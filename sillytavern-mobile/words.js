// shortcut: text inside tracker HTML still counts, strip known tracker tags if the count looks off
export const countWords = text => String(text ?? '').replace(/<[^>]*>/g, ' ').split(/\s+/).filter(Boolean).length;
