import { extension_settings } from '../../../extensions.js';
import { saveSettingsDebounced } from '../../../../script.js';

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
</div>`;

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
