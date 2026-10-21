/** Decorative anatomy only; resistance values are reported separately from the simulation. */
export function UrinaryTractIllustration({ className }: { className?: string | undefined }) {
  return (
    <img
      className={className}
      src="/images/urinary-tract.png"
      alt="Illustration of the urinary tract: two kidneys, two ureters and the bladder"
      width={1024}
      height={1536}
    />
  )
}
