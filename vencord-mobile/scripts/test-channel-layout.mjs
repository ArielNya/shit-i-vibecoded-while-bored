import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const projectRoot = resolve(import.meta.dirname, "..");
const puppeteerEntry = resolve(projectRoot, ".vendor/Vencord/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js");
const { default: puppeteer } = await import(pathToFileURL(puppeteerEntry));
const outputDirectory = resolve(projectRoot, "build/test-results");
await mkdir(outputDirectory, { recursive: true });

const browser = await puppeteer.connect({ browserURL: "http://127.0.0.1:9222", defaultViewport: null });

const delay = milliseconds => new Promise(resolvePromise => setTimeout(resolvePromise, milliseconds));

try {
    const page = (await browser.pages()).find(candidate => candidate.url().includes("canary.discord.com/channels"));
    if (!page) throw new Error("Discord Canary page was not found");
    const originalPath = new URL(page.url()).pathname;

    await page.keyboard.press("Escape");
    await page.evaluate(() => {
        if (!document.querySelector(".vc-settings-tab")) return;
        const close = Array.from(document.querySelectorAll("button[aria-label]"))
            .find(element => element.getAttribute("aria-label") === "Fechar" || element.getAttribute("aria-label") === "Close");
        if (close instanceof HTMLElement) close.click();
    });
    await delay(500);

    if (!await page.$('[class*="channelTextArea_"]')) {
        const navigated = await page.evaluate(() => {
            const links = Array.from(document.querySelectorAll("a[href*='/channels/']"));
            const destination = links.find(element => {
                const rect = element.getBoundingClientRect();
                const path = new URL(element.href).pathname;
                return rect.width > 0 && rect.height > 0 && /^\/channels\/(?:@me|\d+)\/\d+/.test(path);
            });
            if (!(destination instanceof HTMLElement)) return false;
            destination.click();
            return true;
        });
        if (!navigated) throw new Error("No visible channel or DM destination was available for layout testing");
    }

    await page.waitForSelector('[class*="channelTextArea_"]', { visible: true, timeout: 20_000 });
    await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1, hasTouch: false, isMobile: false });
    await page.waitForFunction(() => Boolean(globalThis.Vencord?.Plugins?.plugins?.MobileUX), { timeout: 20_000 });
    await page.evaluate(() => {
        const plugin = globalThis.Vencord.Plugins.plugins.MobileUX;
        globalThis.Vencord.Settings.plugins.MobileUX.activation = "on";
        if (!plugin.started) globalThis.Vencord.Plugins.startPlugin(plugin);
        globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_OPEN" });
    });
    await delay(750);
    await page.evaluate(() => {
        const destination = Array.from(document.querySelectorAll("a[href]"))
            .filter(element => element instanceof HTMLAnchorElement
                && new URL(element.href).pathname === location.pathname
                && element.getBoundingClientRect().width > 0)
            .sort((left, right) => right.getBoundingClientRect().width - left.getBoundingClientRect().width)[0];
        if (destination instanceof HTMLElement) destination.click();
    });
    await delay(1200);
    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_CLOSE" }));
    await delay(500);

    const measure = () => page.evaluate(() => {
        const rectFor = selector => {
            const element = Array.from(document.querySelectorAll(selector)).find(candidate => {
                const rect = candidate.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            });
            if (!element) return null;
            const rect = element.getBoundingClientRect();
            return { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) };
        };
        const visible = element => {
            const rect = element.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0 && getComputedStyle(element).visibility !== "hidden";
        };
        const targets = Array.from(document.querySelectorAll("button, [role='button'], [role='menuitem'], [role='option'], [role='tab']"))
            .filter(visible);
        const ancestry = selector => {
            const start = Array.from(document.querySelectorAll(selector)).find(visible);
            const result = [];
            for (let element = start; element && result.length < 6; element = element.parentElement) {
                const rect = element.getBoundingClientRect();
                result.push({
                    className: String(element.className).split(" ").slice(0, 4).join(" "),
                    display: getComputedStyle(element).display,
                    x: Math.round(rect.x), width: Math.round(rect.width)
                });
            }
            return result;
        };
        return {
            viewport: [innerWidth, innerHeight],
            mobileClass: document.documentElement.classList.contains("mux-mobile"),
            sidebarOpenClass: document.documentElement.classList.contains("mux-sidebar-open"),
            documentOverflow: document.documentElement.scrollWidth > innerWidth,
            sidebar: rectFor('[class^="sidebar_"], [class*=" sidebar_"]'),
            chat: rectFor('[class^="chat_"], [class*=" chat_"]'),
            composer: rectFor('[class^="channelTextArea_"], [class*=" channelTextArea_"]'),
            main: rectFor('main, [role="main"]'),
            editor: rectFor('[contenteditable="true"]'),
            form: rectFor('form'),
            members: rectFor('[class^="membersWrap_"], [class*=" membersWrap_"]'),
            sidebarAncestry: ancestry('[class^="sidebar_"], [class*=" sidebar_"]'),
            chatAncestry: ancestry('[class^="chat_"], [class*=" chat_"]'),
            undersizedTargets: targets.map(element => {
                const rect = element.getBoundingClientRect();
                return { width: Math.round(rect.width), height: Math.round(rect.height), label: element.getAttribute("aria-label") || element.getAttribute("role") || element.tagName };
            }).filter(item => item.width < 44 || item.height < 44)
        };
    });

    const report = { closed: await measure() };
    await page.screenshot({ path: resolve(outputDirectory, "canary-channel-closed-390x844.png") });
    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_OPEN" }));
    await delay(500);
    report.sidebarOpen = await measure();
    await page.screenshot({ path: resolve(outputDirectory, "canary-channel-sidebar-390x844.png") });
    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_CLOSE" }));
    await delay(300);

    report.composerInsideViewport = Boolean(report.closed.composer)
        && report.closed.composer.y + report.closed.composer.height <= report.closed.viewport[1];
    report.chatUsesViewport = Boolean(report.closed.chat)
        && report.closed.chat.x === 0
        && report.closed.chat.width === report.closed.viewport[0];
    report.sidebarOverlaysViewport = Boolean(report.sidebarOpen.sidebar)
        && report.sidebarOpen.sidebar.x === 0
        && report.sidebarOpen.sidebar.width <= report.sidebarOpen.viewport[0];

    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_OPEN" }));
    await delay(400);
    report.serverNavigation = await page.evaluate(() => {
        const channel = Array.from(document.querySelectorAll("a[href]"))
            .find(element => element instanceof HTMLAnchorElement
                && /^\/channels\/\d+\/\d+/.test(new URL(element.href).pathname)
                && element.getBoundingClientRect().width > 0);
        if (!(channel instanceof HTMLElement)) return false;
        channel.click();
        return true;
    });
    if (report.serverNavigation) {
        await delay(1200);
        await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_CLOSE" }));
        await delay(400);
        report.serverChannel = await measure();
        report.memberListOpened = await page.evaluate(() => {
            const button = Array.from(document.querySelectorAll("button[aria-label], [role='button'][aria-label]"))
                .find(element => /(?:membros|members)/i.test(element.getAttribute("aria-label") || "")
                    && element.getBoundingClientRect().width > 0);
            if (!(button instanceof HTMLElement)) return false;
            button.click();
            return true;
        });
        if (report.memberListOpened) {
            await delay(500);
            report.memberList = await measure();
        }
    }

    await page.evaluate(path => {
        globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_CLOSE" });
        globalThis.Vencord.Webpack.Common.NavigationRouter?.transitionTo?.(path);
    }, originalPath);

    await writeFile(resolve(outputDirectory, "canary-channel-layout.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
} finally {
    await browser.disconnect();
}
