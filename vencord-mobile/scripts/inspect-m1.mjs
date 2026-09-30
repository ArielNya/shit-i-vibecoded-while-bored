import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const projectRoot = resolve(import.meta.dirname, "..");
const puppeteerEntry = resolve(
    projectRoot,
    ".vendor/Vencord/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js"
);
const { default: puppeteer } = await import(pathToFileURL(puppeteerEntry));
const outputDirectory = resolve(projectRoot, "build/test-results/m1-inspection");
await mkdir(outputDirectory, { recursive: true });

const browser = await puppeteer.connect({
    browserURL: "http://127.0.0.1:9222",
    defaultViewport: null
});

async function measureChat(page) {
    return page.evaluate(() => {
        const patterns = [
            "guilds_", "sidebar_", "chat_", "content_", "membersWrap_",
            "channelTextArea_", "toolbar_", "panels_"
        ];
        return Object.fromEntries(patterns.map(pattern => {
            const element = Array.from(document.querySelectorAll(`[class*="${pattern}"]`))
                .find(candidate => {
                    const rect = candidate.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                });
            if (!element) return [pattern, null];
            const rect = element.getBoundingClientRect();
            return [pattern, {
                className: String(element.className).split(" ").find(name => name.includes(pattern)),
                x: Math.round(rect.x), y: Math.round(rect.y),
                width: Math.round(rect.width), height: Math.round(rect.height)
            }];
        }));
    });
}

try {
    const page = (await browser.pages()).find(candidate => candidate.url().includes("canary.discord.com/channels"));
    if (!page) throw new Error("Discord Canary page was not found");

    await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1, hasTouch: true, isMobile: true });
    await page.waitForFunction(() => Boolean(globalThis.Vencord?.Plugins?.plugins?.MobileUX), { timeout: 30_000 });
    await page.evaluate(() => {
        const plugin = globalThis.Vencord.Plugins.plugins.MobileUX;
        const settings = globalThis.Vencord.Settings.plugins.MobileUX;
        settings.enabled = true;
        settings.activation = "on";
        if (!plugin.started) globalThis.Vencord.Plugins.startPlugin(plugin);
    });
    await page.waitForFunction(() => document.querySelectorAll("button, [role='button']").length > 5, { timeout: 30_000 });
    await new Promise(resolvePromise => setTimeout(resolvePromise, 1000));

    if (await page.$(".vc-settings-tab")) {
        await page.mouse.click(360, 58);
    }
    await new Promise(resolvePromise => setTimeout(resolvePromise, 500));

    const chatLayout = { initial: await measureChat(page) };
    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_CLOSE" }));
    await new Promise(resolvePromise => setTimeout(resolvePromise, 300));
    chatLayout.closed = await measureChat(page);
    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_OPEN" }));
    await new Promise(resolvePromise => setTimeout(resolvePromise, 300));
    chatLayout.open = await measureChat(page);
    await page.evaluate(() => globalThis.Vencord.Webpack.Common.FluxDispatcher.dispatch({ type: "MOBILE_WEB_SIDEBAR_CLOSE" }));

    if (!await page.$(".vc-plugins-grid")) {
        await page.evaluate(() => {
            globalThis.Vencord.Webpack.Common.SettingsRouter.openUserSettings("vencord_plugins");
        });
    }
    await page.waitForSelector(".vc-plugins-grid", { visible: true, timeout: 20_000 });
    await new Promise(resolvePromise => setTimeout(resolvePromise, 750));
    await page.screenshot({ path: resolve(outputDirectory, "plugins-390x844.png") });

    const settingsLayout = await page.evaluate(() => {
        const visible = element => {
            const rect = element.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0 && getComputedStyle(element).visibility !== "hidden";
        };
        const grid = document.querySelector(".vc-plugins-grid");
        const card = Array.from(document.querySelectorAll(".vc-addon-card"))
            .find(element => element.textContent?.includes("MobileUX"));
        const targets = Array.from(document.querySelectorAll(
            ".vc-settings-tab button, .vc-settings-tab [role='button'], .vc-settings-tab [role='switch'], .vc-settings-tab [role='tab']"
        )).filter(visible);
        const small = targets.map(element => {
            const rect = element.getBoundingClientRect();
            return {
                className: String(element.className).split(" ").slice(0, 3).join(" "),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
                label: element.getAttribute("aria-label") || element.getAttribute("role") || element.tagName
            };
        }).filter(item => item.width < 44 || item.height < 44);
        const gridRect = grid?.getBoundingClientRect();
        const cardRect = card?.getBoundingClientRect();
        const ancestors = [];
        for (let element = grid; element && ancestors.length < 10; element = element.parentElement) {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            ancestors.push({
                tag: element.tagName,
                className: String(element.className).split(" ").slice(0, 5).join(" "),
                x: Math.round(rect.x), y: Math.round(rect.y),
                width: Math.round(rect.width), height: Math.round(rect.height),
                display: style.display,
                overflow: `${style.overflowX}/${style.overflowY}`
            });
        }
        return {
            viewport: [innerWidth, innerHeight],
            documentOverflow: document.documentElement.scrollWidth > innerWidth,
            grid: gridRect && {
                x: Math.round(gridRect.x), width: Math.round(gridRect.width),
                columns: getComputedStyle(grid).gridTemplateColumns
            },
            mobileUxCard: cardRect && {
                x: Math.round(cardRect.x), width: Math.round(cardRect.width), height: Math.round(cardRect.height)
            },
            mobileUxCardControls: card && Array.from(card.querySelectorAll("button, [role='button'], [role='switch']"))
                .map(element => ({ tag: element.tagName, className: String(element.className), role: element.getAttribute("role") })),
            ancestors,
            targetCount: targets.length,
            undersized: small
        };
    });

    const openedModal = await page.evaluate(() => {
        const card = Array.from(document.querySelectorAll(".vc-addon-card"))
            .find(element => element.textContent?.includes("MobileUX"));
        const settingsButton = card?.querySelector(".vc-plugins-info-button");
        if (!(settingsButton instanceof HTMLElement)) return false;
        settingsButton.click();
        return true;
    });

    let modalLayout = null;
    if (openedModal) {
        await page.waitForSelector(".vc-settings-modal-content", { visible: true, timeout: 10_000 });
        await new Promise(resolvePromise => setTimeout(resolvePromise, 500));
        await page.screenshot({ path: resolve(outputDirectory, "mobileux-modal-390x844.png") });
        modalLayout = await page.evaluate(() => {
            const content = document.querySelector(".vc-settings-modal-content");
            const dialog = content?.closest("[role='dialog']") || content?.parentElement;
            const contentRect = content?.getBoundingClientRect();
            const dialogRect = dialog?.getBoundingClientRect();
            return {
                content: contentRect && {
                    x: Math.round(contentRect.x), y: Math.round(contentRect.y),
                    width: Math.round(contentRect.width), height: Math.round(contentRect.height)
                },
                dialog: dialogRect && {
                    x: Math.round(dialogRect.x), y: Math.round(dialogRect.y),
                    width: Math.round(dialogRect.width), height: Math.round(dialogRect.height)
                }
            };
        });
    }

    const report = { chatLayout, settingsLayout, openedModal, modalLayout };
    await writeFile(resolve(outputDirectory, "report.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
} finally {
    await browser.disconnect();
}
