import { extension_settings, getContext } from '../../../extensions.js';
import { saveSettingsDebounced } from '../../../../script.js';
import { promptManager } from '../../../openai.js';
import { groupPrompts } from './groups.js';

const NAME = 'sillytavern_mobile';
const defaults = { enabled: true, paige: true, reading: false, font: 17 };
const settings = extension_settings[NAME] = { ...defaults, ...extension_settings[NAME] };

function apply() {
    document.body.classList.toggle('stm-on', settings.enabled);
    document.body.classList.toggle('stm-paige', settings.paige);
    document.body.classList.toggle('stm-reading', settings.enabled && settings.reading);
    document.documentElement.style.setProperty('--stm-font', `${settings.font}px`);
    $('#stm_read').attr('aria-pressed', String(settings.reading));
}

function set(key, value) {
    settings[key] = value;
    apply();
    saveSettingsDebounced();
}

// Some Android browsers don't shrink 100dvh when the keyboard opens; visualViewport always has the visible height.
function syncHeight() {
    document.documentElement.style.setProperty('--stm-vh', `${window.visualViewport.height}px`);
}

const barHtml = `
<div id="stm_bar">
    <button type="button" class="stm-btn stm-primary" id="stm_continue"><i class="fa-solid fa-forward"></i>Continue</button>
    <button type="button" class="stm-btn" id="stm_edit"><i class="fa-solid fa-pencil"></i>Edit last</button>
    <button type="button" class="stm-btn" id="stm_read"><i class="fa-solid fa-book-open"></i>Read</button>
    <button type="button" class="stm-btn" id="stm_prompts_open"><i class="fa-solid fa-sliders"></i>Prompts</button>
</div>`;

// Downloaded from the authors' repos on tap, never bundled (Sola has no licence to redistribute).
// File names match the originals so a preset you already imported by hand is reused.
const PRESETS = [
    { label: 'Sola V3', file: '☀️ 🧡 Sola V3 Flame 🧡 ☀️', url: 'https://raw.githubusercontent.com/pyrxpia/sola-hub/main/presets/' },
    { label: 'Writer\'s Block V2', file: 'Writer\'s Block Unlimited Version 2 (1)', url: 'https://raw.githubusercontent.com/deiomo/Writer-s-Block-Unlimited/main/' },
];

const sheetHtml = `
<div id="stm_prompts" hidden>
    <div class="stm-sheet-head">
        <div class="stm-presets">${PRESETS.map((p, i) => `<button type="button" class="stm-btn" data-preset="${i}">${p.label}</button>`).join('')}</div>
        <div class="stm-search-row">
            <input type="search" id="stm_prompt_search" class="text_pole" placeholder="Search prompts">
            <button type="button" class="stm-btn" id="stm_prompts_close" aria-label="Close"><i class="fa-solid fa-xmark"></i></button>
        </div>
    </div>
    <div id="stm_prompt_list"></div>
</div>`;

const esc = s => String(s).replace(/[&<>"]/g, c => `&#${c.charCodeAt(0)};`);

function renderPrompts() {
    const pm = promptManager;
    const list = $('#stm_prompt_list');
    if (!pm?.activeCharacter) {
        list.html('<p class="stm-empty">Switch the API to Chat Completion to see preset prompts.</p>');
        return;
    }
    const open = new Set(list.find('details[open]').map((_, d) => d.dataset.title).get());
    const enabled = id => !!pm.getPromptOrderEntry(pm.activeCharacter, id)?.enabled;
    const order = pm.getPromptOrderForCharacter(pm.activeCharacter);
    const prompts = order.map(e => ({ ...pm.getPromptById(e.identifier), identifier: e.identifier }));

    list.html(groupPrompts(prompts).map(s => `
        <details class="stm-section" data-title="${esc(s.title)}" ${open.has(s.title) ? 'open' : ''}>
            <summary>${esc(s.title)} <small>${s.items.filter(i => enabled(i.identifier)).length} on</small></summary>
            ${s.items.map(i => `
            <button type="button" class="stm-prompt" role="switch" aria-checked="${enabled(i.identifier)}" data-id="${esc(i.identifier)}" data-group="${esc(i.group ?? '')}">
                <span>${esc(i.name.replace(/\[PICK 1:[^\]]*\]/i, '').trim())}</span>${i.group ? '<small>pick one</small>' : ''}
                <i class="fa-solid ${enabled(i.identifier) ? 'fa-toggle-on' : 'fa-toggle-off'}"></i>
            </button>`).join('')}
        </details>`).join(''));
    $('#stm_prompt_search').trigger('input');
}

// Mirrors PromptManager.handleToggle, plus switching off the rest of a pick-one group.
function togglePrompt(button) {
    const pm = promptManager;
    const { id, group } = button.dataset;
    const entry = pm.getPromptOrderEntry(pm.activeCharacter, id);
    const changed = [id];
    if (!entry.enabled && group) {
        $(`#stm_prompt_list .stm-prompt[data-group="${CSS.escape(group)}"]`).each((_, b) => {
            if (b.dataset.id === id) return;
            pm.getPromptOrderEntry(pm.activeCharacter, b.dataset.id).enabled = false;
            changed.push(b.dataset.id);
        });
    }
    entry.enabled = !entry.enabled;
    const counts = pm.tokenHandler.getCounts();
    changed.forEach(c => counts[c] = null);
    pm.render();
    pm.saveServiceSettings();
    renderPrompts();
}

async function usePreset({ file, url }) {
    if ($('#main_api').val() !== 'openai') {
        toastr.warning('Switch the API to Chat Completion first.');
        return;
    }
    const existing = $('#settings_preset_openai option').filter((_, o) => o.textContent === file);
    if (existing.length) {
        $('#settings_preset_openai').val(existing.val()).trigger('change');
        return;
    }
    try {
        const res = await fetch(url + encodeURIComponent(file) + '.json');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        // Hand the file to ST's own importer so its regex and overwrite prompts still run.
        const transfer = new DataTransfer();
        transfer.items.add(new File([await res.blob()], `${file}.json`, { type: 'application/json' }));
        const input = document.getElementById('openai_preset_import_file');
        input.files = transfer.files;
        input.dispatchEvent(new Event('input', { bubbles: true }));
    } catch (error) {
        toastr.error(`Couldn't download ${file}: ${error.message}`);
    }
}

const settingsHtml = `
<div class="inline-drawer">
    <div class="inline-drawer-toggle inline-drawer-header">
        <b>Mobile Writer</b>
        <div class="inline-drawer-icon fa-solid fa-circle-chevron-down down"></div>
    </div>
    <div class="inline-drawer-content">
        <label class="checkbox_label"><input type="checkbox" id="stm_enabled">Mobile layout and writer bar</label>
        <label class="checkbox_label"><input type="checkbox" id="stm_paige">Paige theme</label>
        <label for="stm_font">Story text size: <span id="stm_font_val"></span>px</label>
        <input type="range" id="stm_font" min="13" max="24" step="1">
    </div>
</div>`;

jQuery(() => {
    $('#send_form').before(barHtml);
    // Same entry point as ST's own "Continue" menu item.
    $('#stm_continue').on('click', () => $('#option_continue').trigger('click'));
    $('#stm_edit').on('click', () => $('#chat .mes[is_user="false"]').last().find('.mes_edit').trigger('click'));
    $('#stm_read').on('click', () => set('reading', !settings.reading));

    $('body').append(sheetHtml);
    const sheet = document.getElementById('stm_prompts');
    $('#stm_prompts_open').on('click', () => { sheet.hidden = false; renderPrompts(); });
    $('#stm_prompts_close').on('click', () => { sheet.hidden = true; });
    $('#stm_prompt_list').on('click', '.stm-prompt', e => togglePrompt(e.currentTarget));
    $('#stm_prompts .stm-presets').on('click', '[data-preset]', e => usePreset(PRESETS[e.currentTarget.dataset.preset]));
    $('#stm_prompt_search').on('input', e => {
        const q = e.target.value.toLowerCase();
        $('#stm_prompt_list .stm-section').each((_, section) => {
            let any = false;
            $(section).find('.stm-prompt').each((_, b) => {
                b.hidden = !!q && !b.textContent.toLowerCase().includes(q);
                any ||= !b.hidden;
            });
            section.hidden = !any;
            if (q) section.open = true;
        });
    });
    const { eventSource, eventTypes } = getContext();
    eventSource.on(eventTypes.OAI_PRESET_CHANGED_AFTER, () => { if (!sheet.hidden) renderPrompts(); });

    $('#extensions_settings2').append(settingsHtml);
    $('#stm_enabled').prop('checked', settings.enabled).on('change', e => set('enabled', e.target.checked));
    $('#stm_paige').prop('checked', settings.paige).on('change', e => set('paige', e.target.checked));
    $('#stm_font_val').text(settings.font);
    $('#stm_font').val(settings.font).on('input', e => {
        $('#stm_font_val').text(e.target.value);
        set('font', Number(e.target.value));
    });

    window.visualViewport?.addEventListener('resize', syncHeight);
    if (window.visualViewport) syncHeight();
    apply();
});
