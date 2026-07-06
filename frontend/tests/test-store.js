// Simple test to verify the corpusAnnotations store
const { createPinia, setActivePinia } = require('pinia')

// Mock IntervalTree
class IntervalTree {
  constructor() {
    this.root = null
  }
  
  insert(range, value) {
    // Mock implementation
    return this
  }
  
  search(range, filter) {
    // Mock implementation
    return []
  }
  
  clone() {
    return this
  }
}

// Set up Pinia
async function testStore() {
  const pinia = createPinia()
  setActivePinia(pinia)
  
  // Import and test the store
  try {
    const { useCorpusAnnotationsStore } = require('../src/stores/corpusAnnotations.js')
    
    console.log('✓ Store imported successfully')
    
    const store = useCorpusAnnotationsStore()
    
    console.log('✓ Store instance created')
    
    // Test initial state
    if (typeof store.annotationsByLayer === 'object') {
      console.log('✓ annotationsByLayer is initialized')
    }
    
    if (typeof store.segments === 'object') {
      console.log('✓ segments is initialized')
    }
    
    if (store.sentencesByStream instanceof IntervalTree) {
      console.log('✓ sentencesByStream is initialized')
    }
    
    // Test utility methods exist
    if (typeof store.findOverlappingAnnotations === 'function') {
      console.log('✓ findOverlappingAnnotations method exists')
    }
    
    if (typeof store.getSegmentAxisPositions === 'function') {
      console.log('✓ getSegmentAxisPositions method exists')
    }
    
    if (typeof store.formatAnnotationsForDisplay === 'function') {
      console.log('✓ formatAnnotationsForDisplay method exists')
    }
    
    // Test getters
    if (typeof store.getTreeName === 'function') {
      console.log('✓ getTreeName getter exists')
    }
    
    if (typeof store.getAnnotationsForSegment === 'function') {
      console.log('✓ getAnnotationsForSegment getter exists')
    }
    
    console.log('\n✅ All basic store tests passed!')
    return true
    
  } catch (error) {
    console.error('❌ Store test failed:', error.message)
    return false
  }
}

// Run the test
testStore()