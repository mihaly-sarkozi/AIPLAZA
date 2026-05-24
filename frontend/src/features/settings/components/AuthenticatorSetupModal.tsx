import { QRCodeSVG } from "qrcode.react";
import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import type { AuthenticatorSetupResponse } from "../../../api/services/authenticatorService";

type AuthenticatorSetupModalProps = {
  open: boolean;
  setupData: AuthenticatorSetupResponse | null;
  step: 1 | 2 | 3;
  code: string;
  confirmPending: boolean;
  androidUrl: string;
  iosUrl: string;
  setStep: (step: 1 | 2 | 3) => void;
  setCode: (value: string) => void;
  onClose: () => void;
  onCopy: (value: string) => void;
  onConfirm: () => void;
};

export default function AuthenticatorSetupModal({
  open,
  setupData,
  step,
  code,
  confirmPending,
  androidUrl,
  iosUrl,
  setStep,
  setCode,
  onClose,
  onCopy,
  onConfirm,
}: AuthenticatorSetupModalProps) {
  if (!open || !setupData) return null;
  return (
    <Modal open onClose={onClose} closeOnOverlay={!confirmPending} panelClassName="max-w-2xl bg-[var(--color-background)]">
      <ModalHeader
        eyebrow="Authenticator varázsló"
        title="Kétfaktoros hitelesítés beállítása"
        description="Kövesd a lépéseket: app letöltés, QR beolvasás, majd a 6 jegyű kód megerősítése."
      />
      <div className="space-y-4">
        {step === 1 ? <DownloadStep androidUrl={androidUrl} iosUrl={iosUrl} /> : null}
        {step === 2 ? <QrStep setupData={setupData} onCopy={onCopy} /> : null}
        {step === 3 ? <ConfirmStep code={code} setCode={setCode} confirmPending={confirmPending} /> : null}
      </div>
      <ModalFooter>
        {step > 1 ? (
          <Button type="button" variant="secondary" onClick={() => setStep(step === 3 ? 2 : 1)} disabled={confirmPending}>
            Vissza
          </Button>
        ) : null}
        {step < 3 ? (
          <Button type="button" onClick={() => setStep(step === 1 ? 2 : 3)} disabled={confirmPending}>
            Tovább
          </Button>
        ) : (
          <Button type="button" onClick={onConfirm} disabled={code.length !== 6 || confirmPending}>
            {confirmPending ? "Megerősítés..." : "Hitelesítés befejezése"}
          </Button>
        )}
        <Button type="button" variant="secondary" onClick={onClose} disabled={confirmPending}>
          Bezárás
        </Button>
      </ModalFooter>
    </Modal>
  );
}

function DownloadStep({ androidUrl, iosUrl }: { androidUrl: string; iosUrl: string }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
      <p className="text-sm font-semibold text-[var(--color-foreground)]">1) Töltsd le az Authenticator alkalmazást</p>
      <p className="mt-1 text-sm text-[var(--color-muted)]">Kérlek töltsd le az appot, majd lépj tovább a QR-kód beolvasásához.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <a
          href={androidUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm text-[var(--color-foreground)] hover:bg-[var(--color-card-muted)]"
        >
          Google Authenticator (Android)
        </a>
        <a
          href={iosUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm text-[var(--color-foreground)] hover:bg-[var(--color-card-muted)]"
        >
          Google Authenticator (iOS)
        </a>
      </div>
    </div>
  );
}

function QrStep({ setupData, onCopy }: { setupData: AuthenticatorSetupResponse; onCopy: (value: string) => void }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
      <p className="text-sm font-semibold text-[var(--color-foreground)]">2) Olvasd be a QR-kódot</p>
      <div className="mt-3 inline-flex rounded border border-[var(--color-border)] bg-white p-2">
        <QRCodeSVG value={setupData.otpauth_uri} size={190} includeMargin bgColor="#ffffff" fgColor="#111827" />
      </div>
      <p className="mt-3 text-xs text-[var(--color-muted)]">Ha nem tudod beolvasni, add meg kézzel ezt a kulcsot:</p>
      <div className="mt-2 rounded border border-[var(--color-border)] bg-[var(--color-card)] p-2">
        <code className="break-all text-xs text-[var(--color-foreground)]">{setupData.secret}</code>
      </div>
      <div className="mt-2 flex gap-2">
        <Button type="button" variant="secondary" onClick={() => onCopy(setupData.secret)}>
          Titkos kulcs másolása
        </Button>
        <Button type="button" variant="secondary" onClick={() => onCopy(setupData.otpauth_uri)}>
          OTP URI másolása
        </Button>
      </div>
    </div>
  );
}

function ConfirmStep({ code, setCode, confirmPending }: { code: string; setCode: (value: string) => void; confirmPending: boolean }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
      <p className="text-sm font-semibold text-[var(--color-foreground)]">3) Validálás</p>
      <p className="mt-1 text-sm text-[var(--color-muted)]">Írd be az appban látható 6 jegyű kódot.</p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="block text-sm text-[var(--color-label)]">
          Authenticator kód
          <input
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="123456"
            maxLength={6}
            className="mt-1 w-40 rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
            disabled={confirmPending}
          />
        </label>
      </div>
    </div>
  );
}
