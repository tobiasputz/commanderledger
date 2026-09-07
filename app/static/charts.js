'use strict';
const chartData=JSON.parse(document.querySelector('#chart-data').textContent);
chartData.forEach((fig,i)=>Plotly.newPlot('chart-'+i,fig.data,fig.layout,{responsive:true,displaylogo:false,modeBarButtonsToRemove:['sendDataToCloud']}));
