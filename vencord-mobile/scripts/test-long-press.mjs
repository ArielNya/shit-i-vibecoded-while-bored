import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const root = resolve(import.meta.dirname, "..");
const { default: puppeteer } = await import(pathToFileURL(resolve(
    root,
    ".vendor/Vencord/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js"
)));
const browser = await puppeteer.connect({ browserURL: "http://127.0.0.1:9222", defaultViewport: null });
const delay = milliseconds => new Promise(resolvePromise => setTimeout(resolvePromise, milliseconds));

try {
    const page = (await browser.pages()).find(candidate => candidate.url().includes("canary.discord.com/channels"));
    if (!page) throw new Error("Discord Canary page was not found");
    const cdp = await page.createCDPSession();
    await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 1 });
    await page.evaluate(() => {
        const plugin = globalThis.Vencord?.Plugins?.plugins?.MobileUX;
        globalThis.__muxProbe = { starts: 0, contexts: 0 };
        if (plugin && !plugin.__muxProbed) {
            const original = plugin.startLongPress;
            plugin.startLongPress = function (...args) {
                globalThis.__muxProbe.starts++;
                return original.apply(this, args);
            };
            plugin.__muxProbed = true;
            document.addEventListener("contextmenu", () => globalThis.__muxProbe.contexts++, true);
        }
    });
    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_OPEN" }));
    await delay(300);
    if (!await page.$('[id^="chat-messages-"]')) {
        await page.evaluate(() => {
            const destination = Array.from(document.querySelectorAll('a[href^="/channels/@me/"]'))
                .find(element => element.getBoundingClientRect().width > 0);
            if (destination instanceof HTMLElement) destination.click();
        });
        await delay(1200);
    }

    async function hold(selector) {
        await page.keyboard.press("Escape");
        const point = await page.evaluate(candidateSelector => {
            const element = Array.from(document.querySelectorAll(candidateSelector)).find(candidate => {
                const rect = candidate.getBoundingClientRect();
                const x = rect.x + rect.width / 2;
                const y = rect.y + rect.height / 2;
                return rect.width > 0 && rect.height > 0 && y > 120 && y < innerHeight - 40 && candidate.contains(document.elementFromPoint(x, y));
            });
            if (!element) return null;
            const rect = element.getBoundingClientRect();
            const x = Math.round(rect.x + rect.width / 2);
            const y = Math.round(rect.y + rect.height / 2);
            return { x, y, viewport: { width: innerWidth, height: innerHeight }, hit: document.elementFromPoint(x, y)?.className?.toString().slice(0, 90) };
        }, selector);
        if (!point) return { targetFound: false, menuOpened: false };
        await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ ...point, radiusX: 1, radiusY: 1 }] });
        await delay(750);
        const duringHold = await page.$$eval('[role="menu"] [role="menuitem"]', elements => elements.length);
        await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
        await delay(300);
        const menuItems = await page.$$eval('[role="menu"] [role="menuitem"]', elements => elements.filter(element => {
            const rect = element.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        }).length);
        return { targetFound: true, menuOpened: menuItems > 0, menuItems, duringHold, point, probe: await page.evaluate(() => globalThis.__muxProbe) };
    }

    const results = {
        runtime: "Discord Canary Chromium touch emulation; Android WebView still required",
        message: await hold('[id^="chat-messages-"]'),
        userAvatar: await hold('[id^="chat-messages-"] [class*="avatar_"]')
    };
    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_OPEN" }));
    await delay(300);
    results.channel = await hold('a[href^="/channels/"]:not([href^="/channels/@me/"])');
    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_CLOSE" }));
    await writeFile(resolve(root, "build/test-results/canary-long-press.json"), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
} finally {
    await browser.disconnect();
}
