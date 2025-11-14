export default function Footer() {
  return (
    <footer className="w-full bg-slate-800 text-slate-400 text-center p-4 text-sm border-t border-slate-700">
      © {new Date().getFullYear()} BrainBankCenter.com – Minden jog fenntartva.
    </footer>
  );
}