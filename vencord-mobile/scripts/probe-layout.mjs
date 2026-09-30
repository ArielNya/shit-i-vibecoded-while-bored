import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const root = resolve(import.meta.dirname, "..");
const puppeteerPath = resolve(root, ".vendor/Vencord/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js");
const { default: puppeteer } = await import(pathToFileURL(puppeteerPath));
const browser = await puppeteer.connect({ browserURL: "http://127.0.0.1:9222", defaultViewport: null });

try {
    let page;
    for (let attempt = 0; attempt < 60; attempt++) {
        page = (await browser.pages()).find(candidate => candidate.url().includes("canary.discord.com/channels"));
        if (page) break;
        await new Promise(resolvePromise => setTimeout(resolvePromise, 1000));
    }
    if (!page) throw new Error("Discord Canary page was not found");
    await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1, hasTouch: true, isMobile: true });
    await page.waitForFunction(() => Boolean(globalThis.Vencord?.Plugins?.plugins?.MobileUX), { timeout: 30_000 });
    await page.evaluate(() => {
        const plugin = globalThis.Vencord.Plugins.plugins.MobileUX;
        globalThis.Vencord.Settings.plugins.MobileUX.activation = "on";
        if (!plugin.started) globalThis.Vencord.Plugins.startPlugin(plugin);
    });
    await new Promise(resolvePromise => setTimeout(resolvePromise, 1500));
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    await new Promise(resolvePromise => setTimeout(resolvePromise, 500));

    const snapshot = () => page.evaluate(() => {
        const read = pattern => Array.from(document.querySelectorAll(`[class*="${pattern}"]`)).map(element => {
            const rect = element.getBoundingClientRect();
            return {
                className: String(element.className),
                x: Math.round(rect.x), width: Math.round(rect.width),
                display: getComputedStyle(element).display,
                transform: getComputedStyle(element).transform
            };
        }).filter(item => item.width > 0).slice(0, 5);
        return {
            roots: read("content__5e434"),
            sidebars: read("sidebar__5e434"),
            chats: read("chat_f75fb0"),
            bodyClasses: document.body.className,
            htmlClasses: document.documentElement.className
        };
    });

    const initial = await snapshot();
    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_CLOSE" }));
    await new Promise(resolvePromise => setTimeout(resolvePromise, 500));
    const closed = await snapshot();
    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_OPEN" }));
    await new Promise(resolvePromise => setTimeout(resolvePromise, 500));
    const opened = await snapshot();
    const settingsRouterKeys = await page.evaluate(() => Object.keys(globalThis.Vencord.Webpack.Common.SettingsRouter));
    console.log(JSON.stringify({ initial, closed, opened, settingsRouterKeys }, null, 2));
} finally {
    await browser.disconnect();
}
