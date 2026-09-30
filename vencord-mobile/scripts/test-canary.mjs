import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const projectRoot = resolve(import.meta.dirname, "..");
const puppeteerEntry = resolve(
    projectRoot,
    ".vendor/Vencord/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js"
);
const { default: puppeteer } = await import(pathToFileURL(puppeteerEntry));

const browser = await puppeteer.connect({
    browserURL: "http://127.0.0.1:9222",
    defaultViewport: null
});

try {
    let page;
    for (let attempt = 0; attempt < 60; attempt++) {
        page = (await browser.pages()).find(candidate => candidate.url().includes("discord.com/channels"));
        if (page) break;
        await new Promise(resolvePromise => setTimeout(resolvePromise, 1000));
    }
    if (!page) throw new Error("Discord channel page did not become available on the debugging port");

    await page.bringToFront();
    const consoleErrors = [];
    page.on("console", message => {
        if (message.type() === "error") consoleErrors.push(message.text());
    });

    // Switching Chromium's mobile-emulation bit reloads Electron's renderer.
    // Do it once before enabling the plugin so the measured passes are stable.
    await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1, hasTouch: true, isMobile: true });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => Boolean(globalThis.Vencord?.Plugins?.plugins?.MobileUX), { timeout: 30_000 });
    await new Promise(resolvePromise => setTimeout(resolvePromise, 1500));

    const bootstrap = await page.evaluate(() => {
        const vencord = globalThis.Vencord;
        const plugin = vencord?.Plugins?.plugins?.MobileUX;
        const pluginSettings = vencord?.Settings?.plugins?.MobileUX;
        if (!plugin || !pluginSettings) throw new Error("MobileUX was not registered in the Canary bundle");

        pluginSettings.enabled = true;
        pluginSettings.activation = "on";
        pluginSettings.density = "comfortable";
        pluginSettings.fontSize = "medium";
        if (!plugin.started) vencord.Plugins.startPlugin(plugin);

        return {
            enabled: pluginSettings.enabled,
            started: plugin.started,
            activation: pluginSettings.activation
        };
    });

    const presets = [
        ["small-phone", 360, 640],
        ["modern-phone", 390, 844],
        ["large-phone", 430, 932],
        ["phone-landscape", 844, 390],
        ["foldable-boundary", 900, 700],
        ["desktop-control", 1100, 800]
    ];
    const results = [];

    for (const [name, width, height] of presets) {
        await page.evaluate(desktopControl => {
            globalThis.Vencord.Settings.plugins.MobileUX.activation = desktopControl ? "auto" : "on";
            if (!desktopControl) {
                globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_CLOSE" });
            }
        }, name === "desktop-control");
        await page.setViewport({ width, height, deviceScaleFactor: 1, hasTouch: true, isMobile: true });
        await new Promise(resolvePromise => setTimeout(resolvePromise, 1500));

        for (let attempt = 0; attempt < 10; attempt++) {
            const ready = await page.evaluate(() => document.querySelectorAll(
                "button, [role='button'], [role='menuitem'], [role='option'], [role='tab']"
            ).length > 0);
            if (ready) break;
            await new Promise(resolvePromise => setTimeout(resolvePromise, 500));
        }

        const result = await page.evaluate(presetName => {
            const elements = Array.from(document.querySelectorAll(
                "button, [role='button'], [role='menuitem'], [role='option'], [role='tab']"
            )).filter(element => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden";
            });
            const undersized = elements
                .map(element => ({
                    tag: element.tagName,
                    role: element.getAttribute("role"),
                    label: element.getAttribute("aria-label") || element.textContent?.trim().slice(0, 50),
                    width: Math.round(element.getBoundingClientRect().width),
                    height: Math.round(element.getBoundingClientRect().height)
                }))
                .filter(item => item.width < 44 || item.height < 44)
                .slice(0, 20);

            const region = pattern => {
                const element = Array.from(document.querySelectorAll(`[class*="${pattern}"]`)).find(candidate => {
                    const rect = candidate.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                });
                if (!element) return null;
                const rect = element.getBoundingClientRect();
                return {
                    x: Math.round(rect.x), y: Math.round(rect.y),
                    width: Math.round(rect.width), height: Math.round(rect.height)
                };
            };

            return {
                name: presetName,
                viewport: [innerWidth, innerHeight],
                mobileClass: document.documentElement.classList.contains("mux-mobile"),
                pluginPresent: Boolean(globalThis.Vencord?.Plugins?.plugins?.MobileUX),
                coarsePointer: matchMedia("(pointer: coarse)").matches,
                horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
                bodyTextLength: document.body.innerText.length,
                shortBodyText: document.body.innerText.length < 200 ? document.body.innerText : null,
                regions: {
                    sidebar: region("sidebar_"),
                    chat: region("chat_"),
                    composer: region("channelTextArea_"),
                    memberList: region("membersWrap_")
                },
                visibleInteractiveElements: elements.length,
                undersized
            };
        }, name);

        if (name !== "desktop-control") {
            await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_OPEN" }));
            await new Promise(resolvePromise => setTimeout(resolvePromise, 250));
            result.sidebarOpen = await page.evaluate(() => {
                const sidebar = Array.from(document.querySelectorAll('[class*="sidebar_"]')).find(element => {
                    const rect = element.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                });
                if (!sidebar) return null;
                const rect = sidebar.getBoundingClientRect();
                const smallTargets = Array.from(sidebar.querySelectorAll("button, [role='button'], [role='menuitem']"))
                    .filter(element => {
                        const target = element.getBoundingClientRect();
                        return target.width > 0 && target.height > 0 && (target.width < 44 || target.height < 44);
                    }).length;
                return {
                    x: Math.round(rect.x), width: Math.round(rect.width),
                    height: Math.round(rect.height), undersizedTargets: smallTargets
                };
            });
            await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_CLOSE" }));
        }

        results.push(result);
    }

    await page.evaluate(() => {
        globalThis.Vencord.Settings.plugins.MobileUX.activation = "on";
    });

    const report = {
        testedAt: new Date().toISOString(),
        url: page.url(),
        bootstrap,
        presets: results,
        mobileUxConsoleErrors: consoleErrors.filter(message => /mobileux|mux-/i.test(message))
    };
    const reportDirectory = resolve(projectRoot, "build/test-results");
    await mkdir(reportDirectory, { recursive: true });
    const reportPath = resolve(reportDirectory, "canary-responsive.json");
    await writeFile(reportPath, JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
} finally {
    await browser.disconnect();
}
