
const VERCEL_API = 'https://agente-documental-tic-seven.vercel.app';

export const API_ROOT =
  window.location.hostname.endsWith('github.io')
    ? VERCEL_API
    : '';
