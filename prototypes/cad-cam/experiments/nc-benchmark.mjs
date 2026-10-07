import {parseNC,NC_PROFILE} from '../src/nc-parser.js';
import {performance} from 'node:perf_hooks';
const records=[];
for(const lines of [1000,10000,50000]){
 global.gc?.();const before=process.memoryUsage(),text=['G91 G1 F100',...Array(lines-1).fill('X1')].join('\n');
 const started=performance.now(),r=parseNC(text,{profile:NC_PROFILE,initial:[0,0,0],unit:'mm',confirmed:true}),elapsed=performance.now()-started,after=process.memoryUsage();
 if(!r.complete||r.blocks.length!==lines||r.segments.length!==lines-1)throw Error('benchmark correctness failed');
 records.push({lines,bytes:Buffer.byteLength(text),moves:r.segments.length,displayPoints:r.pointsCount,elapsedMs:Number(elapsed.toFixed(2)),heapDeltaMiB:Number(((after.heapUsed-before.heapUsed)/1048576).toFixed(2)),rssDeltaMiB:Number(((after.rss-before.rss)/1048576).toFixed(2))});
}
console.log(JSON.stringify({runtime:process.version,platform:process.platform,arch:process.arch,kind:'Node synthetic linear parser only; excludes browser transfer/render/GPU; deltas not peak memory',records},null,2));
