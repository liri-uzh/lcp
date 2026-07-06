<template>
  <div class="annotation-display popover-liri">
    <span
      v-if="stickyPosition.x && stickyPosition.y"
      class="close-button"
      @click="closeDisplay"
    >
      <FontAwesomeIcon :icon="['fas', 'xmark']" />
    </span>

    <table class="popover-table">
      <template v-for="([layer, annotations]) in sortedFilteredAnnotations" :key="`layer-${layer}`">
        <tr v-if="shouldShowLayer(layer)">
          <td @click="toggleLayerFold(layer)">
            <span class="layer-header">
              <span class="fold-indicator">{{ isLayerFolded(layer) ? '▶' : '▼' }}</span>
              <span class="layer-name">{{ layer }}</span>
              <span v-if="showTimestamps(layer, annotations[0])" class="timetag nowrap">
                {{ formatTimestamps(annotations[0]) }}
              </span>
            </span>
            
            <table class="annotation-details-table">
              <template v-for="(annotation, index) in annotations" :key="`${layer}-${index}`">
                <tr v-for="(value, key) in filterAnnotationProperties(layer, annotation)" :key="`${layer}-${index}-${key}`">
                  <td class="property-name">{{ key }}</td>
                  <td class="property-value" v-if="isImageProperty(layer, key)">
                    <span
                      class="image-link"
                      @click="$emit('show-image', value, layer, annotation)"
                      v-html="value"
                    ></span>
                  </td>
                  <td class="property-value" v-else v-html="formatValue(value, layer, key)"></td>
                </tr>
              </template>
            </table>
          </td>
        </tr>
      </template>
    </table>
  </div>
</template>

<script>
import { mapState } from "pinia";

import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import Utils from '@/utils.js';
import { useCorpusAnnotationsStore } from '@/stores/corpusAnnotations';

/**
 * Reusable component for displaying annotations that overlap with specified axis positions
 * 
 * Props:
 * - axisPositions: Array of {axisType, position} objects
 * - corpusConfig: Corpus configuration
 * - maxAnnotations: Maximum number of annotations to display
 * 
 * Events:
 * - show-image: Emitted when an image annotation should be displayed
 */
export default {
  name: 'AnnotationDisplay',
  components: {
    FontAwesomeIcon
  },
  props: {
    axisPositions: {
      type: Array,
      required: true,
      validator: value => value.every(item =>
        item.axisType && ['stream', 'time', 'location'].includes(item.axisType) &&
        item.position && Array.isArray(item.position)
      )
    },
    maxAnnotations: {
      type: Number,
      default: 50
    },
    stickyPosition: {
      type: Object,
      default: () => ({ x: null, y: null })
    },
    displayPosition: {
      type: Object,
      default: () => ({ x: 0, y: 0 })
    }
  },
  setup() {
    const store = useCorpusAnnotationsStore();
    return { store };
  },
  
  data() {
    return {};
  },
  computed: {
    ...mapState(useCorpusAnnotationsStore, ["corpusConfig", "foldedLayers"]),
    sortedFilteredAnnotations() {
      const ret = Object.entries(this.filteredAnnotations).sort((x,y)=>{
        const layerX = x[0], layerY = y[0];
        if (layerX == this.corpusConfig.firstClass.document) return -1;
        if (Utils.contains(layerX, layerY, this.corpusConfig)) return -1;
        return 1;
      });
      return ret;
    },
    filteredAnnotations() {
      // Get raw annotations from store based on axis positions
      const rawAnnotations = this.store.findOverlappingAnnotations(this.axisPositions);
      
      // Format for display
      return this.store.formatAnnotationsForDisplay(rawAnnotations, this.corpusConfig);
    },
    displayStyle() {
      return {
        top: this.stickyPosition.y 
          ? `min(${this.stickyPosition.y}px, calc(100vh - 33vh))`
          : `${this.displayPosition.y}px`,
        left: `${this.stickyPosition.x || this.displayPosition.x}px`,
        overflowY: (this.stickyPosition.x || this.stickyPosition.y) ? 'scroll' : 'visible',
        maxHeight: this.stickyPosition.y ? '33vh' : 'unset',
      };
    }
  },
  methods: {
    getTreeName(axisType) {
      const mapping = {
        'stream': 'byStream',
        'time': 'byTime', 
        'location': 'byLocation'
      }
      return mapping[axisType] || 'byStream'
    },
    

    
    shouldShowLayer(layer) {
      return this.filteredAnnotations[layer]?.length > 0
    },
    
    filterAnnotationProperties(layer, annotation) {
      if (this.isLayerFolded(layer)) return {};
      return Object.fromEntries(
        Object.entries(annotation).filter(([key,value])=>{
          if (this.isEmpty(value)) return false;
          if (['_id','meta'].includes(key)) return false;
          return true;
        })
      );
    },
    
    isLayerFolded(layer) {
      return this.foldedLayers[layer] || false
    },
    
    toggleLayerFold(layer) {
      this.foldedLayers[layer] = !this.isLayerFolded(layer);
    },
    
    showTimestamps(layer, annotation) {
      return this.corpusConfig.meta?.mediaSlots && 
             'frame_range' in annotation /* &&
             layer == this.corpusConfig.firstClass?.document */;
    },
    
    formatTimestamps(annotation) {
      if (!annotation.frame_range || !this.corpusConfig.firstClass?.document) {
        return ''
      }
      
      const docLayer = this.corpusConfig.firstClass.document
      const docFrameRange = annotation.frame_range
      const docLower = this.filteredAnnotations[docLayer]?.[0]?.frame_range?.[0] || 0
      
      const timestamps = this.getTimestamps(
        ...docFrameRange.map(fr => fr - docLower)
      )
      
      return timestamps.join(' - ')
    },
    
    isImageProperty(layer, property) {
      const layerConfig = this.corpusConfig.layer?.[layer]
      const attributes = layerConfig?.attributes || {}
      
      if (attributes.meta?.[property]?.type === 'image') {
        return true
      }
      
      return attributes[property]?.type === 'image'
    },
    
    formatValue(value) {
      if (this.isEmpty(value)) {
        return ''
      }
      
      if (typeof value === 'object' && value !== null) {
        return Utils.dictToStr(value, { addTitles: true, reorder: x => x[0] === 'id' })
      }
      
      if (Array.isArray(value)) {
        return value.join(', ')
      }
      
      // Handle string values that look like numbers
      if (typeof value === 'string' && value.match(/^0+(\.0+)?$/)) {
        return '<span>0</span>'
      }
      
      return value.toString().trim()
    },
    
    isEmpty(value) {
      if (typeof value === 'number') return false
      if (!value) return true
      if (typeof value === 'object' && Object.keys(value).length === 0) return true
      return false
    },
    
    closeDisplay() {
      this.$emit('close')
    },
    
    getTimestamps(lower_frame, upper_frame) {
      const lfs = lower_frame / 25.0
      const ufs = upper_frame / 25.0
      let min_l = Math.floor(lfs / 60)
      let min_u = Math.floor(ufs / 60)
      let sec_l = Math.round(100 * (lfs % 60)) / 100
      let sec_u = Math.round(100 * (ufs % 60)) / 100
      
      if (min_l < 10) min_l = `0${min_l}`
      if (min_u < 10) min_u = `0${min_u}`
      if (sec_l < 10) sec_l = `0${sec_l}`
      if (sec_u < 10) sec_u = `0${sec_u}`
      
      return [`${min_l}:${sec_l}`, `${min_u}:${sec_u}`]
    },
    
  }
}
</script>

<style scoped>
/* .annotation-display {
  position: fixed;
  background: #cfcfcf;
  padding: 7px;
  border: #cbcbcb 1px solid;
  border-radius: 5px;
  z-index: 200;
} */

.layer-header {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.fold-indicator {
  margin-right: 5px;
  font-size: 0.8em;
}

.layer-name {
  font-weight: bold;
  margin-right: 5px;
}

.timetag {
  display: inline-block;
  white-space: nowrap;
  font-size: 0.8em;
  background: beige;
  box-shadow: 0px 0px 3px black;
  border-radius: 0.25em;
  padding: 2px 5px;
  margin-left: 5px;
}

.timetag.nowrap {
  width: unset;
  white-space: nowrap;
}

.annotation-details-table {
  border-radius: 4px;
  background-color: #ffffff82;
  margin-top: 5px;
  margin-bottom: 10px;
}

.annotation-details-table td {
  padding: 2px 5px;
}

.property-name {
  font-weight: bold;
  padding-right: 10px;
  vertical-align: top;
}

.property-value {
  max-width: 50vw;
}

.image-link {
  cursor: pointer;
  color: blue;
  text-decoration: underline;
}

.close-button {
  position: absolute;
  right: 7px;
  top: 2px;
  cursor: pointer;
  font-size: 0.9em;
}

.popover-table {
  margin-bottom: 0;
  padding: 5px;
}
</style>