import Button from "../../../../components/ui/Button";
import PageHeader from "../../../../components/ui/PageHeader";

type KBListHeaderProps = {
  isOwner: boolean;
  billingRestricted: boolean;
  actionLoading: boolean;
  billingOverviewPending: boolean;
  t: (key: string) => string;
  onOpenTraffic: () => void;
  onCreate: () => void;
};

export default function KBListHeader({
  isOwner,
  billingRestricted,
  actionLoading,
  billingOverviewPending,
  t,
  onOpenTraffic,
  onCreate,
}: KBListHeaderProps) {
  return (
    <PageHeader
      eyebrow={t("kb.collectionLabel")}
      title={t("kb.title")}
      description={t("kb.pageIntro")}
      actions={
        isOwner ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={onOpenTraffic}>
              {t("nav.traffic")}
            </Button>
            {!billingRestricted ? (
              <Button onClick={onCreate} disabled={actionLoading || billingOverviewPending}>
                {t("kb.newKb")}
              </Button>
            ) : null}
          </div>
        ) : null
      }
    />
  );
}
