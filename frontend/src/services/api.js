const API_BASE = '/api';

export async function fetchMuseumMeta() {
  const res = await fetch(`${API_BASE}/curator/exhibition`);
  if (!res.ok) throw new Error('Failed to fetch exhibition meta');
  return res.json();
}

export async function fetchGalleries() {
  const res = await fetch(`${API_BASE}/museum/galleries`);
  if (!res.ok) throw new Error('Failed to fetch galleries');
  return res.json();
}

export async function fetchExhibits(galleryId, page = 1, pageSize = 12) {
  const res = await fetch(`${API_BASE}/museum/exhibits/${galleryId}?page=${page}&pageSize=${pageSize}`);
  if (!res.ok) throw new Error(`Failed to fetch exhibits for ${galleryId}`);
  return res.json();
}

export async function searchMuseum(query, galleryId = null) {
  let url = `${API_BASE}/museum/search?query=${encodeURIComponent(query)}`;
  if (galleryId) url += `&gallery=${encodeURIComponent(galleryId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}

export async function askGuideChat(message, history = []) {
  const res = await fetch(`${API_BASE}/guide/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history })
  });
  if (!res.ok) throw new Error('Guide chat failed');
  return res.json();
}

export async function fetchTimelineEvents() {
  const res = await fetch(`${API_BASE}/timeline/events`);
  if (!res.ok) throw new Error('Failed to fetch timeline events');
  return res.json();
}
