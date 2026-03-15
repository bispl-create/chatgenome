"use client";

import { useEffect, useMemo, useRef, useState } from "react";

declare global {
  interface Window {
    igv?: {
      createBrowser: (
        element: HTMLElement,
        config: {
          genome: string;
          locus: string;
          tracks: Array<Record<string, unknown>>;
        },
      ) => Promise<any>;
    };
  }
}

type AnnotationItem = {
  contig: string;
  pos_1based: number;
  ref: string;
  alts: string[];
  gene: string;
  consequence: string;
  rsid: string;
  clinical_significance: string;
};

type Props = {
  buildGuess: string | null;
  annotations: AnnotationItem[];
  selectedIndex: number;
};

function resolveGenome(buildGuess: string | null) {
  if (buildGuess?.includes("GRCh37")) {
    return "hg19";
  }
  if (buildGuess?.includes("GRCh38")) {
    return "hg38";
  }
  return "hg19";
}

function buildLocus(annotation: AnnotationItem | null) {
  if (!annotation) {
    return "chr1:100,316,400-100,316,900";
  }
  const contig = annotation.contig.startsWith("chr") ? annotation.contig : `chr${annotation.contig}`;
  const start = Math.max(annotation.pos_1based - 150, 1);
  const end = annotation.pos_1based + 150;
  return `${contig}:${start}-${end}`;
}

export default function IgvBrowser({ buildGuess, annotations, selectedIndex }: Props) {
  const browserRef = useRef<HTMLDivElement | null>(null);
  const igvInstanceRef = useRef<any>(null);
  const scriptPromiseRef = useRef<Promise<void> | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

  const selectedAnnotation = annotations[selectedIndex] ?? annotations[0] ?? null;
  const locus = buildLocus(selectedAnnotation);
  const genome = resolveGenome(buildGuess);

  const tracks = useMemo(() => {
    if (!annotations.length) {
      return [];
    }
    return [
      {
        name: "Representative Variants",
        type: "annotation",
        format: "bed",
        displayMode: "EXPANDED",
        colorBy: "name",
        features: annotations.map((item) => {
          const chromosome = item.contig.startsWith("chr") ? item.contig : `chr${item.contig}`;
          return {
            chr: chromosome,
            start: item.pos_1based - 1,
            end: item.pos_1based,
            name: `${item.gene} ${item.rsid}`.trim(),
            description: `${item.ref}>${item.alts.join(",")} | ${item.consequence} | ClinVar ${item.clinical_significance}`,
            color:
              item.clinical_significance !== "." ? "#8b1e1e" : item.consequence === "splice_acceptor_variant" ? "#6d1352" : "#223f58",
          };
        }),
      },
    ];
  }, [annotations]);

  useEffect(() => {
    let cancelled = false;

    function ensureIgvScript() {
      if (typeof window === "undefined") {
        return Promise.resolve();
      }
      if (window.igv?.createBrowser) {
        return Promise.resolve();
      }
      if (scriptPromiseRef.current) {
        return scriptPromiseRef.current;
      }

      scriptPromiseRef.current = new Promise<void>((resolve, reject) => {
        const existing = document.querySelector<HTMLScriptElement>('script[data-igv-browser="true"]');
        if (existing) {
          existing.addEventListener("load", () => resolve(), { once: true });
          existing.addEventListener("error", () => reject(new Error("Failed to load IGV browser script")), {
            once: true,
          });
          return;
        }

        const script = document.createElement("script");
        script.src = "/vendor/igv.min.js";
        script.async = true;
        script.dataset.igvBrowser = "true";
        script.onload = () => resolve();
        script.onerror = () => reject(new Error("Failed to load IGV browser script"));
        document.head.appendChild(script);
      });

      return scriptPromiseRef.current;
    }

    async function renderBrowser() {
      if (!browserRef.current || !annotations.length) {
        setRenderError(null);
        return;
      }

      await ensureIgvScript();
      if (cancelled) {
        return;
      }

      const igvApi = window.igv;
      if (!igvApi) {
        throw new Error("IGV browser script loaded but window.igv is unavailable");
      }

      if (igvInstanceRef.current) {
        igvInstanceRef.current.removeAllTracks?.();
        igvInstanceRef.current.loadTrackList?.(tracks);
        igvInstanceRef.current.search?.(locus);
        return;
      }

      if (typeof igvApi.createBrowser !== "function") {
        throw new Error("IGV module did not expose createBrowser");
      }

      igvInstanceRef.current = await igvApi.createBrowser(browserRef.current, {
        genome,
        locus,
        tracks,
      });
      setRenderError(null);
    }

    renderBrowser().catch((error) => {
      if (!cancelled) {
        const message = error instanceof Error ? error.message : String(error);
        setRenderError(message);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [annotations.length, genome, locus, tracks]);

  return (
    <section className="card">
      <div className="cardHeader">
        <h2>IGV Plot</h2>
        <span className="mono">{genome}</span>
      </div>
      <div className="igvToolbar">
        <div className="miniMeta">
          <span className="label">Locus</span>
          <strong>{locus}</strong>
        </div>
        <div className="miniMeta">
          <span className="label">Selection</span>
          <strong>{selectedAnnotation ? `${selectedAnnotation.gene || "Unknown"} | ${selectedAnnotation.rsid || "no-rsID"}` : "No annotation"}</strong>
        </div>
      </div>
      <div className="igvFrame">
        {renderError ? <p className="errorText">IGV could not be loaded: {renderError}</p> : null}
        <div ref={browserRef} className="igvMount" />
      </div>
    </section>
  );
}
