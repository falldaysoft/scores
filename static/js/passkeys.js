/* Passkey (WebAuthn) helpers, built on @simplewebauthn/browser (global SimpleWebAuthnBrowser). */
(function () {
  if (!window.SimpleWebAuthnBrowser) {
    console.error('SimpleWebAuthnBrowser not loaded');
    return;
  }
  var startRegistration = window.SimpleWebAuthnBrowser.startRegistration;
  var startAuthentication = window.SimpleWebAuthnBrowser.startAuthentication;

  function getCsrfToken() {
    var el = document.querySelector('input[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
  }

  async function postJson(url, data) {
    var resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify(data || {}),
    });
    var payload = null;
    try { payload = await resp.json(); } catch (e) { /* no body */ }
    if (!resp.ok) {
      throw new Error((payload && payload.error) || ('Request failed (' + resp.status + ')'));
    }
    return payload;
  }

  // Register a new passkey for the logged-in user. `name` is an optional label.
  window.registerPasskey = async function (beginUrl, completeUrl, name) {
    var optionsJSON = await postJson(beginUrl, {});
    var attResp = await startRegistration({ optionsJSON: optionsJSON });
    return await postJson(completeUrl, { credential: attResp, name: name || '' });
  };

  // Usernameless login: let the browser offer discoverable passkeys for this site.
  window.loginWithPasskey = async function (beginUrl, completeUrl) {
    var optionsJSON = await postJson(beginUrl, {});
    var authResp = await startAuthentication({ optionsJSON: optionsJSON });
    return await postJson(completeUrl, authResp);
  };

  window.passkeysSupported = function () {
    return typeof window.PublicKeyCredential !== 'undefined';
  };
})();
