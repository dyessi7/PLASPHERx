// SPHEREx detectors and their wavelength coverage in microns.
// Ranges are approximate, verify against the SPHEREx instrument documentation.
export const DETECTORS = [
  { id: 'D1', min: 0.75, max: 1.11 },
  { id: 'D2', min: 1.1, max: 1.65 },
  { id: 'D3', min: 1.64, max: 2.42 },
  { id: 'D4', min: 2.42, max: 3.82 },
  { id: 'D5', min: 3.82, max: 4.42 },
  { id: 'D6', min: 4.42, max: 5.0 },
]

export const DETECTOR_IDS = DETECTORS.map((d) => d.id)

// One color per detector, validated for contrast and color-blind separation
// on the dark surface.
export const DETECTOR_COLORS = {
  D1: '#3987e5',
  D2: '#d95926',
  D3: '#199e70',
  D4: '#c98500',
  D5: '#d55181',
  D6: '#008300',
}

export const DEFAULT_DETECTOR = 'D2'
export const DEFAULT_FOV = 0.1

export const FIELD_LIMITS = {
  ra: { min: 0, max: 360 },
  dec: { min: -90, max: 90 },
  fov: { min: 0.02, max: 0.5 },
}

// Known objects worth looking at. The buttons only fill in the search form.
export const SUGGESTED_TARGETS = [
  { name: 'R Draconis', ra: 248.1675, dec: 66.755, fov: 0.1 },
  { name: 'RW Aurigae', ra: 76.9564, dec: 30.4014, fov: 0.1 },
  { name: "Barnard's Star", ra: 269.4463, dec: 4.7682, fov: 0.1 },
  { name: 'WISE 0855', ra: 133.7599, dec: -7.2422, fov: 0.1 },
  { name: 'Epsilon Indi B', ra: 331.096, dec: -56.801, fov: 0.2 },
]
