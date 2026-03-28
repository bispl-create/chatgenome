"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type PreviewVariant = {
  available: boolean;
  image_data_url: string | null;
  message: string;
  label?: string;
};

type ViewerFile = {
  fileName: string;
  preview?: PreviewVariant;
  preview_presets?: Record<string, PreviewVariant>;
};

type ViewerSeriesGroup = {
  id: string;
  label: string;
  files: ViewerFile[];
};

type ViewerProps = {
  seriesGroups: ViewerSeriesGroup[];
};

const WINDOW_PRESETS = ["default", "soft", "lung", "bone", "brain"] as const;

export default function DicomInteractiveViewer({ seriesGroups }: ViewerProps) {
  const [selectedSeriesId, setSelectedSeriesId] = useState(seriesGroups[0]?.id ?? "");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [windowPreset, setWindowPreset] = useState<(typeof WINDOW_PRESETS)[number]>("default");
  const [cinePlaying, setCinePlaying] = useState(false);
  const dragRef = useRef<{ active: boolean; startX: number; startY: number; baseX: number; baseY: number }>({
    active: false,
    startX: 0,
    startY: 0,
    baseX: 0,
    baseY: 0,
  });

  useEffect(() => {
    setSelectedSeriesId(seriesGroups[0]?.id ?? "");
    setCurrentIndex(0);
    setZoom(1);
    setOffset({ x: 0, y: 0 });
    setWindowPreset("default");
    setCinePlaying(false);
  }, [seriesGroups]);

  const selectedSeries = useMemo(
    () => seriesGroups.find((group) => group.id === selectedSeriesId) ?? seriesGroups[0] ?? null,
    [selectedSeriesId, seriesGroups],
  );

  const files = selectedSeries?.files ?? [];
  const activeFile = files[currentIndex] ?? null;
  const activePreview =
    (activeFile?.preview_presets && activeFile.preview_presets[windowPreset]) || activeFile?.preview || null;

  useEffect(() => {
    if (!cinePlaying || files.length <= 1) {
      return;
    }
    const interval = window.setInterval(() => {
      setCurrentIndex((current) => (current + 1) % files.length);
    }, 250);
    return () => window.clearInterval(interval);
  }, [cinePlaying, files.length]);

  function resetView() {
    setZoom(1);
    setOffset({ x: 0, y: 0 });
    setCinePlaying(false);
    setWindowPreset("default");
  }

  function beginPan(event: React.MouseEvent<HTMLDivElement>) {
    dragRef.current = {
      active: true,
      startX: event.clientX,
      startY: event.clientY,
      baseX: offset.x,
      baseY: offset.y,
    };
  }

  function movePan(event: React.MouseEvent<HTMLDivElement>) {
    if (!dragRef.current.active) {
      return;
    }
    const deltaX = event.clientX - dragRef.current.startX;
    const deltaY = event.clientY - dragRef.current.startY;
    setOffset({
      x: dragRef.current.baseX + deltaX,
      y: dragRef.current.baseY + deltaY,
    });
  }

  function endPan() {
    dragRef.current.active = false;
  }

  function handleWheel(event: React.WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    if (event.shiftKey && files.length > 1) {
      setCurrentIndex((current) => {
        const next = current + (event.deltaY > 0 ? 1 : -1);
        return Math.max(0, Math.min(next, files.length - 1));
      });
      return;
    }
    setZoom((current) => Math.max(0.25, Math.min(current + (event.deltaY < 0 ? 0.1 : -0.1), 6)));
  }

  return (
    <div className="dicomViewerShell">
      <div className="dicomViewerToolbar">
        <div className="dicomViewerControls">
          <label className="viewerSelectWrap">
            <span>Series</span>
            <select
              value={selectedSeriesId}
              onChange={(event) => setSelectedSeriesId(event.target.value)}
              className="viewerSelect"
            >
              {seriesGroups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="viewerControlButton"
            onClick={() => setCurrentIndex((current) => Math.max(0, current - 1))}
            disabled={currentIndex <= 0}
          >
            Prev
          </button>
          <button
            type="button"
            className="viewerControlButton"
            onClick={() => setCurrentIndex((current) => Math.min(files.length - 1, current + 1))}
            disabled={!files.length || currentIndex >= files.length - 1}
          >
            Next
          </button>
          <button type="button" className="viewerControlButton" onClick={() => setZoom((current) => Math.min(current + 0.15, 6))}>
            Zoom +
          </button>
          <button type="button" className="viewerControlButton" onClick={() => setZoom((current) => Math.max(current - 0.15, 0.25))}>
            Zoom -
          </button>
          <button
            type="button"
            className="viewerControlButton"
            onClick={() => setCinePlaying((current) => !current)}
            disabled={files.length <= 1}
          >
            {cinePlaying ? "Pause" : "Cine Play"}
          </button>
          <button type="button" className="viewerControlButton" onClick={resetView}>
            Reset
          </button>
        </div>
        <div className="dicomViewerMeta">
          <span>{activePreview?.message ?? "Preview not available"}</span>
          <span>
            Slice {files.length ? currentIndex + 1 : 0}/{files.length}
          </span>
        </div>
      </div>
      <div className="dicomViewerPresetRow">
        {WINDOW_PRESETS.map((preset) => (
          <button
            key={preset}
            type="button"
            className={`viewerPresetButton ${windowPreset === preset ? "viewerPresetButtonActive" : ""}`}
            onClick={() => setWindowPreset(preset)}
          >
            {activeFile?.preview_presets?.[preset]?.label ?? preset}
          </button>
        ))}
      </div>
      <div
        className="dicomViewerCanvas"
        onMouseDown={beginPan}
        onMouseMove={movePan}
        onMouseUp={endPan}
        onMouseLeave={endPan}
        onWheel={handleWheel}
      >
        {activePreview?.available && activePreview.image_data_url ? (
          <img
            src={activePreview.image_data_url}
            alt={activeFile?.fileName ?? "DICOM preview"}
            className="dicomViewerImage"
            style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})` }}
            draggable={false}
          />
        ) : (
          <div className="dicomPreviewPlaceholder dicomViewerEmpty">{activePreview?.message ?? "Preview not available"}</div>
        )}
      </div>
      <p className="dicomViewerHint">Mouse wheel: zoom, Shift + wheel: slice navigation, drag: pan.</p>
    </div>
  );
}
