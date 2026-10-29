"use strict";
function prepareWorksheet(){
  for(const input of document.querySelectorAll('.worksheet textarea,.worksheet select')){
    let output=input.nextElementSibling;
    if(!output?.classList.contains('print-value')){output=document.createElement('div');output.className='print-value';input.after(output);}
    output.textContent=input.value||'Not completed';
  }
}
window.addEventListener('beforeprint',prepareWorksheet);
document.getElementById('printWorksheet').addEventListener('click',()=>{prepareWorksheet();window.print();});
