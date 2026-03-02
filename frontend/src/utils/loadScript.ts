export async function loadScript(src: string): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`) as HTMLScriptElement | null;
    if (existing) {
      if ((existing as any).dataset.loaded === 'true') {
        resolve();
        return;
      }
      existing.addEventListener('load', () => resolve());
      existing.addEventListener('error', () => reject(new Error(`Failed to load script: ${src}`)));
      return;
    }

    const script = document.createElement('script');
    script.src = src;
    script.async = true;
    script.addEventListener('load', () => {
      (script as any).dataset.loaded = 'true';
      resolve();
    });
    script.addEventListener('error', () => reject(new Error(`Failed to load script: ${src}`)));
    document.body.appendChild(script);
  });
}
