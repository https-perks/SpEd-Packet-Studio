const appIconUrl = `${import.meta.env.BASE_URL}app-icon.png`;
const folioAnimationUrl = `${import.meta.env.BASE_URL}folio-wag.webp`;

interface FolioSplashProps {
  readonly message?: string;
}

export function FolioSplash({ message = "Preparing your studio..." }: FolioSplashProps) {
  return (
    <div className="folio-splash" role="status" aria-live="polite">
      <div className="folio-splash__orb" aria-hidden="true">
        <span className="folio-splash__ring folio-splash__ring--outer" />
        <span className="folio-splash__ring folio-splash__ring--inner" />
        <picture>
          <source srcSet={folioAnimationUrl} type="image/webp" />
          <img className="folio-splash__fox" src={appIconUrl} alt="" />
        </picture>
      </div>
      <div className="folio-splash__copy">
        <p className="folio-splash__eyebrow">Folio is getting things ready</p>
        <h1>SpEd Packet Studio</h1>
        <p>{message}</p>
      </div>
      <div className="folio-splash__progress" aria-hidden="true">
        <span />
      </div>
    </div>
  );
}
