import { fluent } from './fluent';

export function t (id, args = {}) {
  const bundle = fluent.bundles[0];
  const msg = bundle.getMessage(id);
  if (!msg) return id;
  return bundle.formatPattern(msg.value, args, /* errors */ []);
}
