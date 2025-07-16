import { FluentBundle, FluentResource } from '@fluent/bundle';
import { createFluentVue } from 'fluent-vue';
import enMessages from './locales/en.ftl';
import itMessages from './locales/it.ftl';
import frMessages from './locales/fr.ftl';

export const availableLanguages = [
  { name: 'English', value: 'en', messages: enMessages },
  { name: 'Italiano', value: 'it', messages: itMessages },
  { name: 'Français', value: 'fr', messages: frMessages }
]
const defaultLocale = availableLanguages[0]

// Create bundles for locales that will be used
const bundles = Object.fromEntries(availableLanguages.map(({value, messages})=>{
  const bundle = new FluentBundle(value);
  bundle.addResource(new FluentResource(messages));
  return [value, bundle];
}));

// Function to get the user’s preferred locale
export function getUserLocale() {
  try {
    const saved = localStorage.getItem('locale');
    if (saved) {
      // console.log('Got previously chosen language', JSON.parse(saved))
      return JSON.parse(saved);
    }
  } catch (e) {
    console.error('Error parsing locale from localStorage:', e);
  }

  // Otherwise, check the browser language
  const browserLocale = navigator.language || navigator.userLanguage;
  // If the browser language starts with "it", use Italian; otherwise default to English
  const locale = availableLanguages.find(({value})=>browserLocale && browserLocale.toLowerCase().startsWith(value));
  if (locale)
    return locale;

  return defaultLocale;
}

const initialLocale = getUserLocale();

// Create plugin istance
// bundles - The current negotiated fallback chain of languages
export const fluent = createFluentVue({
  bundles: [initialLocale.value in bundles ? bundles[initialLocale.value] : bundles.en]
});

export function changeLocale(locale) {
  // localStorage.setItem('locale', locale);
  // console.log('language changed', locale);
  localStorage.setItem('locale', JSON.stringify(locale));

  if (locale.value in bundles)
    fluent.bundles = [bundles[locale.value]];
  else
    fluent.bundles = [bundles.en];
}
