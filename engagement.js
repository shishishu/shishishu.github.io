const namespace = location.hostname === 'shishishu.github.io'
  ? 'shishishu.github.io'
  : 'shishishu-preview.test';
const storageKey = 'homepage-liked';
const likeButton = document.querySelector('#like-button');
const likeCount = document.querySelector('#like-count');
const statusMessage = document.querySelector('#like-status');
let liked = false;
try {
  liked = localStorage.getItem(storageKey) !== null;
} catch {
  // Storage can be disabled. Keep the interaction available for this page load.
}

async function counter(operation, key) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), key === 'views' ? 30000 : 8000);
  try {
    const response = await fetch(`https://abacus.jasoncameron.dev/${operation}/${namespace}/${key}`, {
      cache: 'no-store',
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
      signal: controller.signal,
    });
    if (operation === 'get' && response.status === 404) return 0;
    if (!response.ok) throw new Error('Counter unavailable');
    const { value } = await response.json();
    if (!Number.isSafeInteger(value) || value < 0) throw new Error('Invalid count');
    return value;
  } finally {
    clearTimeout(timer);
  }
}

function updateLikeButton() {
  const label = liked ? 'You liked this page' : 'Like this page';
  likeButton.title = label;
  likeButton.setAttribute('aria-label', `${label}. Likes: ${likeCount.textContent}`);
  likeButton.classList.toggle('liked', liked);
  likeButton.disabled = liked;
}

likeButton.addEventListener('click', async () => {
  likeButton.disabled = true;
  statusMessage.textContent = '';
  try {
    const total = await counter('hit', 'likes');
    likeCount.textContent = total.toLocaleString();
    liked = true;
    try {
      localStorage.setItem(storageKey, String(total));
    } catch {
      // The in-memory flag still prevents repeat clicks.
    }
    statusMessage.textContent = 'Liked!';
  } catch {
    statusMessage.textContent = 'Couldn’t confirm your like. Try again.';
  } finally {
    updateLikeButton();
  }
});

document.querySelector('#engagement').hidden = false;
const viewCount = document.querySelector('#view-count');
const viewsKey = `homepage-views:${namespace}`;
let lastViews = null;

function showSavedViews(raw) {
  if (raw === null || !/^\d+$/.test(raw)) return;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || (lastViews !== null && value <= lastViews)) return;
  lastViews = value;
  viewCount.textContent = value.toLocaleString();
  viewCount.title = 'Last confirmed view count';
}

async function refreshViews() {
  try {
    const stored = localStorage.getItem(viewsKey);
    showSavedViews(stored);
  } catch {
    // Visitors who block storage still get the shared server count.
  }

  let total;
  try {
    total = await counter('hit', 'views');
  } catch {
    // The increment may already have reached the server. Only read it back.
    try {
      total = await counter('get', 'views');
    } catch {
      if (lastViews === null) viewCount.textContent = 'unavailable';
      return;
    }
  }
  showSavedViews(String(total));
  try {
    showSavedViews(localStorage.getItem(viewsKey));
    localStorage.setItem(viewsKey, String(lastViews));
  } catch {
    // The current page can still display the confirmed count.
  }
}

refreshViews();
counter('get', 'likes')
  .then(total => { likeCount.textContent = total.toLocaleString(); })
  .catch(() => { likeCount.textContent = '—'; })
  .finally(updateLikeButton);

window.addEventListener('storage', event => {
  if (event.key === viewsKey) showSavedViews(event.newValue);
  if (event.key === storageKey && event.newValue !== null) {
    liked = true;
    likeCount.textContent = Number(event.newValue).toLocaleString();
    updateLikeButton();
  }
});
