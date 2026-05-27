// stores/corpusAnnotations.js
import { defineStore } from 'pinia'
import { IntervalTree } from '@/intervaltrees'

class PreparedSegment {
  constructor(sid, offset, content, annotations, char_range) {
    this.id = sid;
    this.offset = offset;
    this.content = content;
    this.annotations = annotations;
    this.char_range = char_range;
  }

  static empty() {
    return new PreparedSegment("", 0, [], {}, [])
  }
}

export const useCorpusAnnotationsStore = defineStore('corpusAnnotations', {
  state: () => {
    return {
    // Core data structures - ONLY data, no display state
    annotationsByLayer: {}, // { layerName: { byId: {}, byStream: IntervalTree, byTime: IntervalTree, byLocation: IntervalTree } }
    segments: {},           // { segmentId: { data: PreparedSegment, annotations: {} } }
    sentencesByStream: new IntervalTree(),
    segmentAnnotations: {},  // { segmentId: { layerName: annotationId[] } }
    corpusConfig: null,

    // Minimal operational state
    loading: false,
    error: null,
    lastUpdated: null
    };
  },

  actions: {
    /**
     * Process backend data and populate the store
     */
    processBackendData(backendData) {
      this.loading = true
      this.error = null

      try {
        if (-1 in backendData) {
          this.processSegments(backendData[-1])
        }

        if (-2 in backendData) {
          this.processAnnotations(backendData[-2])
        }

        this.lastUpdated = new Date()
        this.loading = false

        return true
      } catch (error) {
        this.error = error
        this.loading = false
        console.error('Error processing backend data:', error)
        return false
      }
    },

    /**
     * Process segment data from backend
     */
    processSegments(segmentsData) {
      Object.entries(segmentsData).forEach(([sid, v]) => {
        if (sid in this.segments) return;

        const rangeMatches = v.map(x => String(x || "").match(/^\[(\d+),(\d+)\)$/))
        const rangeIdx = rangeMatches.findIndex(x => x)

        if (rangeIdx >= 0) {
          const range = rangeMatches[rangeIdx].slice(1,).map(x => parseInt(x))
          range[1] = range[1] - 1;
          v[rangeIdx] = range
          this.sentencesByStream.insert(range, sid)
        }

        this.segments[sid] = {
          data: new PreparedSegment(sid, ...v),
          annotations: {}
        }
      })
    },

    /**
     * Process annotation data from backend
     */
    processAnnotations(metaData) {
      const META_LIMIT = 50000
      const processedCount = Math.min(metaData.length, META_LIMIT)

      if (metaData.length > META_LIMIT) {
        console.warn(`Too much metadata (over ${META_LIMIT} lines) - processing first ${META_LIMIT} items`)
      }

      for (let i = 0; i < processedCount; i++) {
        const [sids, layer, lid, info] = metaData[i]
        if (!lid) continue

        if (!(layer in this.annotationsByLayer)) {
          this.annotationsByLayer[layer] = {
            byId: {},
            byStream: new IntervalTree(),
            byTime: new IntervalTree(),
            byLocation: new IntervalTree()
          }
        }

        const layerData = this.annotationsByLayer[layer]
        if (lid in layerData.byId) continue

        info._id = lid
        layerData.byId[lid] = info

        for (let sid of sids) {
          if (!this.segments[sid]) {
            this.segments[sid] = {
              data: PreparedSegment.empty(),
              annotations: {}
            }
          }
          this.segments[sid].annotations[layer] = lid

          if (!this.segmentAnnotations[sid]) {
            this.segmentAnnotations[sid] = {}
          }
          if (!this.segmentAnnotations[sid][layer]) {
            this.segmentAnnotations[sid][layer] = []
          }
          this.segmentAnnotations[sid][layer].push(lid)
        }

        this.indexAnnotationAnchors(layerData, info)
      }
    },

    /**
     * Index annotation by its spatial/temporal anchors
     */
    indexAnnotationAnchors(layerData, info) {
      const anchorTypes = {
        char_range: { tree: 'byStream', adjustEnd: true },
        frame_range: { tree: 'byTime', adjustEnd: true },
        xy_box: { tree: 'byLocation', adjustEnd: false }
      }

      for (const [anchorProp, config] of Object.entries(anchorTypes)) {
        if (!(anchorProp in info)) continue

        let range = info[anchorProp]
          .split(",")
          .map(x => parseInt(x.replace(/[[()]/g, "")))

        if (config.adjustEnd && range.length >= 2) {
          range = range.map((v, i) => i === 1 ? v - 1 : v)
        }

        info[anchorProp] = range
        this.insertIntoIntervalTree(layerData[config.tree], range, info)
      }
    },

    /**
     * Insert annotation into appropriate interval tree
     */
    insertIntoIntervalTree(tree, range, value) {
      if (range.length === 4) {
        const [x1, y1, x2, y2] = range
        const xs = [x1, x2].sort((a, b) => a - b)
        const ys = [y1, y2].sort((a, b) => a - b)

        let xTree = tree.search(xs, n => n.low === xs[0] && n.high === xs[1])[0]?.value
        if (!xTree) {
          xTree = new IntervalTree()
          tree.insert(xs, xTree)
        }
        xTree.insert(ys, value)
      } else if (range.length === 2) {
        const [start, end] = range
        tree.insert([start, end], value)
      }
    },

    // ===== INTEGRATED UTILITY METHODS =====

    /**
     * Find annotations overlapping with given axis positions
     * @param {Array} axisPositions - Array of {axisType, position} objects
     * @returns {Object} - Annotations grouped by layer
     */
    findOverlappingAnnotations(axisPositions) {
      const results = {}

      axisPositions.forEach(axisPos => {
        const { axisType, position } = axisPos
        const treeName = this.getTreeName(axisType)

        Object.entries(this.annotationsByLayer).forEach(([layer, layerData]) => {
          if (!layerData[treeName]) return

          const matches = layerData[treeName].search(position, () => true)
          matches.forEach(node => {
            const annotation = node.value
            if (!results[layer]) results[layer] = []
            if (!results[layer].some(a => a._id === annotation._id)) {
              results[layer].push(annotation)
            }
          })
        })
      })

      return results
    },

    /**
     * Get axis positions for a segment
     * @param {string} segmentId - Segment ID
     * @returns {Array} - Array of axis position objects
     */
    getSegmentAxisPositions(segmentId) {
      const segment = this.segments[segmentId]?.data
      if (!segment) return []

      const positions = []

      const char_range = segment.char_range;

      if (char_range) {
        positions.push({
          axisType: 'stream',
          position: char_range
        })
      }

      if (this.corpusConfig === undefined)
        return positions;

      const segmentLayerName = this.corpusConfig.firstClass?.segment;
      const annotationsBySegment = this.annotationsByLayer[segmentLayerName];
      const segmentAnnotations = annotationsBySegment ? annotationsBySegment[segmentId] : null;

      if (!segmentAnnotations)
        return positions;

      if (segmentAnnotations.frame_range) {
        positions.push({
          axisType: 'time',
          position: segmentAnnotations.frame_range
        })
      }

      if (segmentAnnotations.xy_box) {
        positions.push({
          axisType: 'location',
          position: segmentAnnotations.xy_box
        })
      }

      return positions
    },

    /**
     * Format annotations for display
     * @param {Object} annotationsByLayer - Raw annotations data
     * @returns {Object} - Formatted annotations
     */
    formatAnnotationsForDisplay(annotationsByLayer) {
      const formatted = {}
      const allowedProperties = this.calculateAllowedProperties();

      Object.entries(annotationsByLayer).forEach(([layer, annotations]) => {
        if (!allowedProperties[layer]) return

        formatted[layer] = annotations.map(annotation => {
          const formattedAnnotation = { ...annotation }

          // Handle meta properties
          if (formattedAnnotation.meta && typeof formattedAnnotation.meta === 'object') {
            Object.assign(formattedAnnotation, formattedAnnotation.meta)
            delete formattedAnnotation.meta
          }

          // Format numeric strings
          Object.keys(formattedAnnotation).forEach(key => {
            if (typeof formattedAnnotation[key] === 'string' &&
                formattedAnnotation[key].match(/^0+(\.0+)?$/)) {
              formattedAnnotation[key] = '0'
            }
          })

          return formattedAnnotation
        })
      })

      return formatted
    },

    /**
     * Calculate allowed properties for each layer
     */
    calculateAllowedProperties() {
      const allowed = {}

      Object.keys(this.corpusConfig?.layer || {}).forEach(layer => {
        if (this.corpusConfig.layer[layer]?.attributes) {
          allowed[layer] = [
            ...Object.keys(this.corpusConfig.layer[layer].attributes),
            ...Object.keys(this.corpusConfig.layer[layer].attributes?.meta || {})
          ]

          if (allowed[layer].includes('meta')) {
            delete allowed.meta
          }

          if (this.corpusConfig.meta?.mediaSlots && layer === this.corpusConfig.firstClass?.document) {
            allowed[layer].push('name')
          }
        }
      })

      return allowed
    }
  },

  getters: {
    /**
     * Get interval tree name for axis type
     */
    getTreeName: () => (axisType) => {
      const mapping = {
        'stream': 'byStream',
        'time': 'byTime',
        'location': 'byLocation'
      }
      return mapping[axisType] || 'byStream'
    },

    getSegmentAnnotations: (state) => () => {
      const segLayerName = state.corpusConfig?.firstClass?.segment;
      if (!segLayerName) return {};
      return state.annotationsByLayer[segLayerName] || {};
    },

    getDocumenttAnnotations: (state) => () => {
      const docLayerName = state.corpusConfig?.firstClass?.document;
      if (!docLayerName) return {};
      return state.annotationsByLayer[docLayerName] || {};
    },

    /**
     * Get all annotations for a segment
     */
    getAnnotationsForSegment: (state) => (segmentId) => {
      if (!state.segments[segmentId]?.annotations) return {}

      const result = {}
      Object.entries(state.segments[segmentId].annotations).forEach(([layer, annotationId]) => {
        const annotation = state.annotationsByLayer[layer]?.byId[annotationId]
        if (annotation) {
          result[layer] = annotation
        }
      })
      return result
    },

    /**
     * Get segment data by ID
     */
    getSegment: (state) => (segmentId) => {
      return state.segments[segmentId]?.data || []
    },

    /**
     * Get segment data by char_range
     * @returns {Array} - Array of [startIndex, tokens, annotations, char_range]
     */
    getSegmentsByCharRange: (state) => (range) => {
      const sids = state.sentencesByStream.searchValue(range);
      return sids
        .filter((x,i,a) => a.slice(i+1,).indexOf(x) < 0) // unique
        .filter(sid => sid in state.segments)            // present
        .map(sid => state.segments[sid].data)            // data
        .sort( (x,y) => {                                // sorted
          return x.char_range[0] - y.char_range[0];
        });
    },


    /**
     * Get document annotations by char_range
     */
    getDocumentByCharRange: (state) => (range) => {
      const docLayerName = state.corpusConfig.firstClass?.document;
      if (!docLayerName) return null;
      const docAnnotations = state.annotationsByLayer[docLayerName];
      if (!docAnnotations) return null;
      const docs = docAnnotations.byStream.searchValue(range);
      return docs.length > 0 ? docs[0] : null;
    },

    /**
     * Get all annotation layers
     */
    getAnnotationLayers: (state) => {
      return Object.keys(state.annotationsByLayer)
    },

    /**
     * Get annotation count by layer
     */
    getAnnotationCountByLayer: (state) => (layer) => {
      return Object.keys(state.annotationsByLayer[layer]?.byId || {}).length
    },

    /**
     * Get total annotation count
     */
    getTotalAnnotationCount: (state) => {
      return Object.values(state.annotationsByLayer).reduce(
        (sum, layer) => sum + Object.keys(layer.byId || {}).length,
        0
      )
    },

    /**
     * Get total segment count
     */
    getTotalSegmentCount: (state) => {
      return Object.keys(state.segments).length
    },

    /**
     * Check if store has data
     */
    hasData: (state) => {
      return state.lastUpdated !== null
    }
  }
})