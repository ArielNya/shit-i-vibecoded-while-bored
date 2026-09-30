import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const root = resolve(import.meta.dirname, "..");
const { default: puppeteer } = await import(pathToFileURL(resolve(root, ".vendor/Vencord/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js")));
const browser = await puppeteer.connect({ browserURL: "http://127.0.0.1:9222", defaultViewport: null });

try {
    const page = (await browser.pages()).find(candidate => candidate.url().includes("canary.discord.com/channels"));
    if (!page) throw new Error("Discord Canary page was not found");
    const row = await page.$('[id^="chat-messages-"] [class*="messageContent_"]');
    if (!row) throw new Error("No message visible for the back test");

    await page.evaluate(() => {
        globalThis.__muxOriginalMobile = globalThis.VencordMobile;
        globalThis.__muxFallbackCalls = 0;
        const plugin = globalThis.Vencord.Plugins.plugins.MobileUX;
        globalThis.__muxBefore = { classes: document.documentElement.className, activation: plugin.settings.store.activation };
        plugin.stop();
        globalThis.VencordMobile = { onBackPress: () => { globalThis.__muxFallbackCalls++; return false; } };
        plugin.start();
        globalThis.__muxAfter = { classes: document.documentElement.className, activation: plugin.settings.store.activation };
    });
    try {
        await row.evaluate(element => element.scrollIntoView({ block: "center" }));
        await new Promise(resolveDelay => setTimeout(resolveDelay, 200));
        const box = await row.boundingBox();
        if (!box) throw new Error("Message row has no visible bounds");
        await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2, { button: "right" });
        await new Promise(resolveDelay => setTimeout(resolveDelay, 300));
        const result = await page.evaluate(() => {
            const menuOpened = !!document.querySelector('[role="menu"]');
            const consumed = globalThis.VencordMobile.onBackPress();
            const menuClosed = !document.querySelector('[role="menu"]');
            const fallbackAfterMenu = globalThis.__muxFallbackCalls;
            const fallbackResult = globalThis.VencordMobile.onBackPress();
            return { before: globalThis.__muxBefore, after: globalThis.__muxAfter, menuOpened, consumed, menuClosed, fallbackAfterMenu, fallbackResult, fallbackCalls: globalThis.__muxFallbackCalls, themeClass: document.documentElement.classList.contains("mux-mobile") };
        });
        console.log(JSON.stringify(result, null, 2));
        if (!result.menuOpened || !result.consumed || !result.menuClosed || result.fallbackAfterMenu !== 0 || result.fallbackCalls !== 1 || !result.themeClass) process.exitCode = 1;
    } finally {
        await page.evaluate(() => {
            const plugin = globalThis.Vencord.Plugins.plugins.MobileUX;
            plugin.stop();
            globalThis.VencordMobile = globalThis.__muxOriginalMobile;
            delete globalThis.__muxOriginalMobile;
            delete globalThis.__muxFallbackCalls;
            plugin.start();
        });
    }
} finally {
    await browser.disconnect();
}
