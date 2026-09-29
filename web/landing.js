/* Faultline landing page. Two jobs: pull the real alert text from the API so
   it is never a stale copy, and mark which nav section you are reading. */

const $ = (id) => document.getElementById(id);

/* The alert block on the page is the same string the agent matches against, so
   it is fetched rather than duplicated. If the API is unreachable the block
   stays empty and says so, rather than showing something invented. */
async function loadAlert() {
  const pre = $('alert-clip');
  if (!pre) return;
  pre.textContent = 'Loading the alert from the API...';
  try {
    const r = await fetch('/api/corpus');
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    pre.textContent = data.live_alert.alert_text;
  } catch {
    pre.textContent =
      'The alert text could not be loaded from the API. Start the server with ./run.sh and reload.';
  }
}

/* Mark the nav item for the section currently in view. IntersectionObserver
   rather than a scroll handler, because a scroll handler on every frame is
   work this page does not need. */
function markCurrentSection() {
  const links = [...document.querySelectorAll('.masthead-nav a[href^="#"]')];
  const targets = links
    .map((a) => document.querySelector(a.getAttribute('href')))
    .filter(Boolean);
  if (!targets.length) return;

  const set = (id) => {
    links.forEach((a) => {
      if (a.getAttribute('href') === '#' + id) a.setAttribute('aria-current', 'true');
      else a.removeAttribute('aria-current');
    });
  };

  const io = new IntersectionObserver(
    (entries) => {
      const visible = entries.filter((e) => e.isIntersecting);
      if (visible.length) set(visible[0].target.id);
    },
    { rootMargin: '-20% 0px -60% 0px', threshold: 0 }
  );
  targets.forEach((t) => io.observe(t));
  set(targets[0].id);
}

loadAlert();
markCurrentSection();
