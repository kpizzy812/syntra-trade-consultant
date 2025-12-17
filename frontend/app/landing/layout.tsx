import UTMTracker from "@/components/analytics/UTMTracker";

export default function LandingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      {/* Автоматически отслеживает UTM параметры при загрузке страницы */}
      <UTMTracker />
      {children}
    </>
  );
}
