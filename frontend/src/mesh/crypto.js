export async function signPacket(packet) {
  const text = JSON.stringify(packet);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return btoa(String.fromCharCode(...new Uint8Array(digest))).slice(0, 32);
}
