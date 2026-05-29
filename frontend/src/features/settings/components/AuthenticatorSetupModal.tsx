// frontend/src/features/settings/components/AuthenticatorSetupModal.tsx
// Feladat: Legacy authenticator setup wizard modal komponens.
// Sárközi Mihály - 2026.05.29

import { QRCodeSVG } from "qrcode.react";
import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import type { AuthenticatorSetupResponse } from "../../../api/services/authenticatorService";

export type AuthenticatorSetupModalLabels = {
  eyebrow: string;
  title: string;
  description: string;
  back: string;
  next: string;
  close: string;
  confirmPending: string;
  confirmAction: string;
  downloadTitle: string;
  downloadDescription: string;
  qrTitle: string;
  qrManualHint: string;
  copySecret: string;
  copyOtpUri: string;
  validateTitle: string;
  validateDescription: string;
  codeLabel: string;
};

type AuthenticatorSetupModalProps = {
  open: boolean;
  setupData: AuthenticatorSetupResponse | null;
  labels: AuthenticatorSetupModalLabels;
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
  labels,
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
        eyebrow={labels.eyebrow}
        title={labels.title}
        description={labels.description}
      />
      <div className="space-y-4">
        {step === 1 ? <DownloadStep androidUrl={androidUrl} iosUrl={iosUrl} labels={labels} /> : null}
        {step === 2 ? <QrStep setupData={setupData} onCopy={onCopy} labels={labels} /> : null}
        {step === 3 ? <ConfirmStep code={code} setCode={setCode} confirmPending={confirmPending} labels={labels} /> : null}
      </div>
      <ModalFooter>
        {step > 1 ? (
          <Button type="button" variant="secondary" onClick={() => setStep(step === 3 ? 2 : 1)} disabled={confirmPending}>
            {labels.back}
          </Button>
        ) : null}
        {step < 3 ? (
          <Button type="button" onClick={() => setStep(step === 1 ? 2 : 3)} disabled={confirmPending}>
            {labels.next}
          </Button>
        ) : (
          <Button type="button" onClick={onConfirm} disabled={code.length !== 6 || confirmPending}>
            {confirmPending ? labels.confirmPending : labels.confirmAction}
          </Button>
        )}
        <Button type="button" variant="secondary" onClick={onClose} disabled={confirmPending}>
          {labels.close}
        </Button>
      </ModalFooter>
    </Modal>
  );
}

function DownloadStep({ androidUrl, iosUrl, labels }: { androidUrl: string; iosUrl: string; labels: AuthenticatorSetupModalLabels }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
      <p className="text-sm font-semibold text-[var(--color-foreground)]">{labels.downloadTitle}</p>
      <p className="mt-1 text-sm text-[var(--color-muted)]">{labels.downloadDescription}</p>
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

function QrStep({ setupData, onCopy, labels }: { setupData: AuthenticatorSetupResponse; onCopy: (value: string) => void; labels: AuthenticatorSetupModalLabels }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
      <p className="text-sm font-semibold text-[var(--color-foreground)]">{labels.qrTitle}</p>
      <div className="mt-3 inline-flex rounded border border-[var(--color-border)] bg-white p-2">
        <QRCodeSVG value={setupData.otpauth_uri} size={190} includeMargin bgColor="#ffffff" fgColor="#111827" />
      </div>
      <p className="mt-3 text-xs text-[var(--color-muted)]">{labels.qrManualHint}</p>
      <div className="mt-2 rounded border border-[var(--color-border)] bg-[var(--color-card)] p-2">
        <code className="break-all text-xs text-[var(--color-foreground)]">{setupData.secret}</code>
      </div>
      <div className="mt-2 flex gap-2">
        <Button type="button" variant="secondary" onClick={() => onCopy(setupData.secret)}>
          {labels.copySecret}
        </Button>
        <Button type="button" variant="secondary" onClick={() => onCopy(setupData.otpauth_uri)}>
          {labels.copyOtpUri}
        </Button>
      </div>
    </div>
  );
}

function ConfirmStep({
  code,
  setCode,
  confirmPending,
  labels,
}: {
  code: string;
  setCode: (value: string) => void;
  confirmPending: boolean;
  labels: AuthenticatorSetupModalLabels;
}) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
      <p className="text-sm font-semibold text-[var(--color-foreground)]">{labels.validateTitle}</p>
      <p className="mt-1 text-sm text-[var(--color-muted)]">{labels.validateDescription}</p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="block text-sm text-[var(--color-label)]">
          {labels.codeLabel}
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
