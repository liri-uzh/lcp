// Simple test to verify component structure
const fs = require('fs');

console.log('Testing Vue component structure...\n');

const components = [
  'AnnotationDisplay.vue',
  'SegmentTable.vue'
];

components.forEach(component => {
  const path = `../src/components/${component}`;
  try {
    const content = fs.readFileSync(path, 'utf8');
    
    // Check for required sections
    const hasTemplate = content.includes('<template>') && content.includes('</template>');
    const hasScript = content.includes('<script>') && content.includes('</script>');
    const hasStyle = content.includes('<style>') && content.includes('</style>');
    const hasName = content.match(/name:\s*["']\w+["']/);
    const hasProps = content.includes('props:');
    const hasData = content.includes('data()');
    const hasMethods = content.includes('methods:');
    
    console.log(`${component}:`);
    console.log(`  ✓ Template: ${hasTemplate}`);
    console.log(`  ✓ Script: ${hasScript}`);
    console.log(`  ✓ Style: ${hasStyle}`);
    console.log(`  ✓ Component name: ${hasName ? 'defined' : 'missing'}`);
    console.log(`  ✓ Props: ${hasProps ? 'defined' : 'missing'}`);
    console.log(`  ✓ Data: ${hasData ? 'defined' : 'missing'}`);
    console.log(`  ✓ Methods: ${hasMethods ? 'defined' : 'missing'}`);
    
    // Check for common Vue syntax issues
    const templateErrors = [];
    if (content.match(/<template>[\s\S]*<\/template>[\s\S]*<template>/)) {
      templateErrors.push('Multiple template sections');
    }
    
    if (content.match(/<script>[\s\S]*<\/script>[\s\S]*<script>/)) {
      templateErrors.push('Multiple script sections');
    }
    
    if (templateErrors.length > 0) {
      console.log(`  ✗ Errors: ${templateErrors.join(', ')}`);
    } else {
      console.log(`  ✓ No structural errors detected`);
    }
    
    console.log('');
  } catch (err) {
    console.log(`${component}: ✗ Error reading file: ${err.message}\n`);
  }
});

console.log('Component structure test completed.');