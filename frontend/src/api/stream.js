// Returns the manifest URL string for hls.js — no axios needed
export const getManifestUrl = (videoId) => `/stream/${videoId}/index.m3u8`
