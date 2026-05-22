const fs = require('fs');
const src = fs.readFileSync(
  'C:\\Users\\VIJAY SALVATORE\\Desktop\\Projects\\RAG\\frontend\\src\\pages\\History.jsx',
  'utf8'
);
const opens = (src.match(/<(motion\.)?div/g) || []).length;
const closes = (src.match(/<\/(motion\.)?div>/g) || []).length;
console.log('open <div/<motion.div:', opens);
console.log('close:</div>            :', closes);
console.log('balanced               :', opens === closes ? 'YES' : 'NO');
