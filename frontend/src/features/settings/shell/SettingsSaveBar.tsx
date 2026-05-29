// frontend/src/features/settings/shell/SettingsSaveBar.tsx
// Feladat: A settings mentés/mégse gombsor shell-szintű komponense.
// Sárközi Mihály - 2026.05.29

import Button from "../../../components/ui/Button";

type SettingsSaveBarProps = {
  cancelLabel: string;
  saveLabel: string;
  loadingLabel: string;
  disabled: boolean;
  onCancel: () => void;
  onSave: () => void;
};

export default function SettingsSaveBar({ cancelLabel, saveLabel, loadingLabel, disabled, onCancel, onSave }: SettingsSaveBarProps) {
  return (
    <div className="flex justify-end gap-2">
      <Button type="button" variant="secondary" onClick={onCancel} disabled={disabled}>
        {cancelLabel}
      </Button>
      <Button type="button" onClick={onSave} disabled={disabled}>
        {disabled ? loadingLabel : saveLabel}
      </Button>
    </div>
  );
}
