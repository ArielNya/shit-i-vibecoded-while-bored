import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";

import { chromium } from "playwright-core";

const root = new URL("..", import.meta.url);
const css = readFileSync(new URL("theme/MobileUX.theme.css", root), "utf8");
const fixture = new URL("test/fixture.html", root).href;
const vencordParser = new URL(".cache/Vencord/src/main/themes/index.ts", root);

test("Vencord's theme parser reads the header", { skip: !existsSync(vencordParser) && "run scripts/build-vencord.sh to fetch Vencord" }, async () => {
    const { getThemeInfo } = await import(vencordParser.href);
    const info = getThemeInfo(css, "MobileUX.theme.css");
    assert.equal(info.name, "MobileUX");
    assert.equal(info.author, "ArielNya");
    assert.equal(info.version, "0.1.0");
    assert.match(info.description, /^Touch-friendly/);
});

async function open(contextOptions) {
    const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || "/opt/pw-browsers/chromium" });
    const page = await (await browser.newContext(contextOptions)).newPage();
    await page.goto(fixture);
    await page.addStyleTag({ content: css });
    return { browser, page };
}

const style = (page, sel, prop) => page.$eval(sel, (el, p) => getComputedStyle(el)[p], prop);

test("Chromium keeps every rule block", async () => {
    const { browser, page } = await open({});
    const count = await page.evaluate(() => {
        const sheet = [...document.styleSheets].at(-1);
        const media = [...sheet.cssRules].find(r => r instanceof CSSMediaRule);
        return media.cssRules.length;
    });
    await browser.close();
    const source = css.slice(css.indexOf("@media")).replace(/\/\*[\s\S]*?\*\//g, "");
    const expected = (source.match(/\{/g).length - 1); // minus the @media block itself
    assert.equal(count, expected);
});

test("applies on a phone", async () => {
    const { browser, page } = await open({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    try {
        assert.equal(await style(page, "#channel", "minHeight"), "44px");
        assert.equal((await style(page, "#grid", "gridTemplateColumns")).split(" ").length, 1);
        assert.equal(await style(page, "#hover-btn", "minHeight"), "36px");
        assert.equal(await style(page, "#plugin-modal", "borderRadius"), "0px");

        await page.focus("#msg");
        assert.equal(await style(page, "#hover-bar", "opacity"), "1");
    } finally {
        await browser.close();
    }
});

test("does nothing on desktop", async () => {
    const { browser, page } = await open({ viewport: { width: 1280, height: 800 } });
    try {
        assert.notEqual(await style(page, "#channel", "minHeight"), "44px");
        await page.focus("#msg");
        assert.equal(await style(page, "#hover-bar", "opacity"), "0");
    } finally {
        await browser.close();
    }
});

test("does nothing on a narrow desktop window (mouse, not touch)", async () => {
    const { browser, page } = await open({ viewport: { width: 390, height: 844 } });
    try {
        assert.notEqual(await style(page, "#channel", "minHeight"), "44px");
    } finally {
        await browser.close();
    }
});
