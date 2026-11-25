const namespace = location.hostname === 'shishishu.github.io'
  ? 'shishishu.github.io'
  : 'shishishu-preview.test';
const storageKey = 'homepage-liked';
const likeButton = document.querySelector('#like-button');
const likeCount = document.querySelector('#like-count');
const statusMessage = document.querySelector('#like-status');

function readStored(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key, value) {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    // The current page still works when storage is blocked.
  }
}

function cachedCount(key, element) {
  let last = null;

  function show(raw) {
    if (raw === null || !/^\d+$/.test(raw)) return;
    const value = Number(raw);
    if (!Number.isSafeInteger(value) || (last !== null && value <= last)) return;
    last = value;
    element.textContent = value.toLocaleString();
    element.title = 'Last confirmed count';
  }

  show(readStored(key));
  return {
    key,
    show,
    confirm(total) {
      show(readStored(key));
      show(total);
      writeStored(key, last);
    },
    unavailable() {
      if (last === null) element.textContent = 'unavailable';
    },
  };
}

const likes = cachedCount(`homepage-likes:${namespace}`, likeCount);
const views = cachedCount(`homepage-views:${namespace}`, document.querySelector('#view-count'));
// Older versions only saved a total when the visitor liked the page.
const previousLike = readStored(storageKey);
let liked = previousLike !== null;
let submittingLike = false;
likes.show(previousLike);

async function counter(operation, key) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
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
  likeButton.disabled = liked || submittingLike;
}

likeButton.addEventListener('click', async () => {
  if (liked || submittingLike) return;
  submittingLike = true;
  updateLikeButton();
  statusMessage.textContent = '';
  try {
    const total = await counter('hit', 'likes');
    liked = true;
    writeStored(storageKey, total);
    likes.confirm(total);
    statusMessage.textContent = 'Liked!';
  } catch {
    statusMessage.textContent = 'Couldn’t confirm your like.';
    refreshLikes();
  } finally {
    submittingLike = false;
    updateLikeButton();
  }
});

document.querySelector('#engagement').hidden = false;
updateLikeButton();

async function refreshViews() {
  let total;
  try {
    total = await counter('hit', 'views');
  } catch {
    // The increment may already have reached the server. Only read it back.
    try {
      total = await counter('get', 'views');
    } catch {
      views.unavailable();
      return;
    }
  }
  views.confirm(total);
}

async function refreshLikes() {
  try {
    likes.confirm(await counter('get', 'likes'));
  } catch {
    likes.unavailable();
  }
  updateLikeButton();
}

async function loadLikesSnapshot() {
  try {
    const response = await fetch('./assets/likes.json', { cache: 'no-cache' });
    if (!response.ok) return;
    const { value } = await response.json();
    if (Number.isSafeInteger(value) && value >= 0) {
      likes.confirm(value);
      updateLikeButton();
    }
  } catch {
    // The live request and the browser's cached count work independently.
  }
}

refreshViews();
if (namespace === 'shishishu.github.io') loadLikesSnapshot();
refreshLikes();

window.addEventListener('storage', event => {
  if (event.key === views.key) views.show(event.newValue);
  if (event.key === likes.key) {
    likes.show(event.newValue);
    updateLikeButton();
  }
  if (event.key === storageKey && event.newValue !== null) {
    liked = true;
    likes.show(event.newValue);
    updateLikeButton();
  }
});
