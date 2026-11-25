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
  const response = await fetch(`https://abacus.jasoncameron.dev/${operation}/${namespace}/${key}`, {
    cache: 'no-store',
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    signal: AbortSignal.timeout(8000),
  });
  if (operation === 'get' && response.status === 404) return 0;
  if (!response.ok) throw new Error('Counter unavailable');
  const { value } = await response.json();
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Invalid count');
  return value;
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
counter('hit', 'views')
  .then(total => { viewCount.textContent = total.toLocaleString(); })
  .catch(() => { viewCount.textContent = '—'; });
counter('get', 'likes')
  .then(total => { likeCount.textContent = total.toLocaleString(); })
  .catch(() => { likeCount.textContent = '—'; })
  .finally(updateLikeButton);

window.addEventListener('storage', event => {
  if (event.key === storageKey && event.newValue !== null) {
    liked = true;
    likeCount.textContent = Number(event.newValue).toLocaleString();
    updateLikeButton();
  }
});
