import { FluentBundle, FluentResource } from '@fluent/bundle';
import { createFluentVue } from 'fluent-vue';
import enMessages from './locales/en.ftl';
import itMessages from './locales/it.ftl';

export const availableLanguages = [
  { name: 'English', value: 'en' },
  { name: 'Italiano', value: 'it' }
]
const defaultLocale = availableLanguages[0]

// Create bundles for locales that will be used
const enBundle = new FluentBundle('en');
enBundle.addResource(new FluentResource(enMessages));
const itBundle = new FluentBundle('it');
itBundle.addResource(new FluentResource(itMessages));

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
  if (browserLocale && browserLocale.toLowerCase().startsWith('en')) {
    return { name: 'English', value: 'en' };
  } else if (browserLocale && browserLocale.toLowerCase().startsWith('it')) {
    return { name: 'Italiano', value: 'it' };
  }

  return defaultLocale;
}

const initialLocale = getUserLocale();

// Create plugin istance
// bundles - The current negotiated fallback chain of languages
export const fluent = createFluentVue({
  bundles: [initialLocale.value === 'en' ? enBundle : itBundle]
});

export function changeLocale(locale) {
  // localStorage.setItem('locale', locale);
  // console.log('language changed', locale);
  localStorage.setItem('locale', JSON.stringify(locale));

  if (locale.value === 'en') {
    fluent.bundles = [enBundle];
  } else if (locale.value === 'it') {
    fluent.bundles = [itBundle];
  } else {
    fluent.bundles = [enBundle];
  }
}
