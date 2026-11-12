export default function Loader({ fullPage = false, label = 'Loading…' }) {
  return (
    <div className={fullPage ? 'loader loader-full' : 'loader'} role="status">
      <span className="spinner" />
      <span>{label}</span>
    </div>
  );
}
