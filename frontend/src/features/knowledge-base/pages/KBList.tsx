import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useKbList, useCreateKbMutation, useDeleteKbMutation, type KbItem } from "../hooks/useKb";

export default function KBList() {
  const { data: items = [], isLoading: loading } = useKbList();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createError, setCreateError] = useState("");
  const navigate = useNavigate();
  const location = useLocation();

  const createKbMutation = useCreateKbMutation();
  const deleteKbMutation = useDeleteKbMutation();
  const createLoading = createKbMutation.isPending;

  useEffect(() => {
    if ((location.state as { openKbCreate?: boolean })?.openKbCreate) {
      setShowCreateModal(true);
      setCreateName("");
      setCreateDescription("");
      setCreateError("");
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  const openCreateModal = () => {
    setCreateName("");
    setCreateDescription("");
    setCreateError("");
    setShowCreateModal(true);
  };

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError("");
    createKbMutation.mutate(
      { name: createName.trim(), description: createDescription.trim() },
      {
        onSuccess: () => setShowCreateModal(false),
        onError: (err: unknown) => {
          setCreateError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Hiba történt.");
        },
      }
    );
  };

  const deleteKB = (kb: KbItem) => {
    const confirmName = window.prompt(
      `Törlés megerősítése.\nÍrd be a tudástár nevét: "${kb.name}"`
    );

    if (confirmName !== kb.name) {
      alert("A beírt név nem egyezik.");
      return;
    }
    if (confirmName == null) return;

    deleteKbMutation.mutate({ uuid: kb.uuid, confirm_name: confirmName });
  };

  if (loading) return <div className="p-10 text-[var(--color-foreground)]">Betöltés...</div>;

  return (
    <div className="p-6 min-h-full bg-[var(--color-background)]">
      <div className="flex flex-nowrap items-center gap-3 mb-6 min-w-0 w-full">
        <h1 className="min-w-0 flex-1 text-xl sm:text-2xl md:text-3xl font-bold truncate text-[var(--color-foreground)]">
          Tudástárak
        </h1>
        <button
          type="button"
          onClick={openCreateModal}
          className="ml-auto shrink-0 bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] px-4 py-2 rounded text-sm"
        >
          Új tudástár
        </button>
      </div>

      <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-[var(--color-table-head)]">
            <tr>
              <th className="p-3 text-left text-[var(--color-foreground)]">Név</th>
              <th className="p-3 text-left text-[var(--color-foreground)]">Leírás</th>
              <th className="p-3 text-left text-[var(--color-foreground)]">Műveletek</th>
            </tr>
          </thead>
          <tbody>
            {items.map((kb: KbItem) => (
              <tr key={kb.uuid} className="border-t border-[var(--color-border)]">
                <td className="p-3 text-[var(--color-foreground)]">{kb.name}</td>
                <td className="p-3 text-[var(--color-muted)]">{kb.description}</td>
                <td className="p-3">
                  <div className="flex gap-2 justify-end flex-wrap">
                    <button
                      className="bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] px-3 py-1 rounded text-sm"
                      onClick={() => navigate(`/kb/edit/${kb.uuid}`)}
                    >
                      Szerkesztés
                    </button>
                    <button
                      className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded text-sm"
                      onClick={() => deleteKB(kb)}
                    >
                      Törlés
                    </button>
                    <button
                      className="bg-[var(--color-card)] hover:opacity-80 text-[var(--color-foreground)] border border-[var(--color-border)] px-3 py-1 rounded text-sm"
                      onClick={() => navigate(`/kb/train/${kb.uuid}`)}
                    >
                      Tanítás
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg w-96 shadow-lg">
            <h2 className="text-2xl font-bold mb-4 text-[var(--color-foreground)]">Új tudástár</h2>
            {createError && (
              <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
                {createError}
              </div>
            )}
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block mb-1 text-[var(--color-foreground)]">Név</label>
                <input
                  type="text"
                  value={createName}
                  onChange={(e) => {
                    setCreateName(e.target.value);
                    if (createError) setCreateError("");
                  }}
                  className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
                  placeholder="Tudástár neve"
                  maxLength={20}
                  required
                />
              </div>
              <div>
                <label className="block mb-1 text-[var(--color-foreground)]">Leírás</label>
                <textarea
                  value={createDescription}
                  onChange={(e) => setCreateDescription(e.target.value)}
                  className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded h-28 resize-y"
                  placeholder="Opcionális leírás"
                />
              </div>
              <div className="flex gap-2 mt-6 justify-end">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    setCreateError("");
                  }}
                  disabled={createLoading}
                  className="bg-[var(--color-card)] hover:opacity-80 text-[var(--color-foreground)] border border-[var(--color-border)] px-4 py-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Mégse
                </button>
                <button
                  type="submit"
                  disabled={createLoading}
                  className="bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] px-4 py-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {createLoading ? "Mentés…" : "Mentés"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
