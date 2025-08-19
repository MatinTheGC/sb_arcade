self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // If it's the Adobe SWZ request, swap to current host
  if (
    url.hostname === 'fpdownload.adobe.com' &&
    url.pathname === '/pub/swz/tlf/1.0.0.595/textLayout_1.0.0.595.swz'
  ) {
    const localUrl = new URL(url.pathname, self.location.origin);
    // Mirror the original request settings
    event.respondWith(fetch(localUrl.toString(), event.request));
  }
});
