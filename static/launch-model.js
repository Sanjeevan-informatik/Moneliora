"use strict";
(function(root){
  function model(p){
    const limits={price:[1,100000],vat:[0,50],refund:[0,100],feePercent:[0,20],feeFixed:[0,100],delivery:[0,100000],hours:[.25,100],hourly:[0,10000],capacity:[0,48],acquisitionHours:[0,48],visitors:[0,1e7],leadRate:[0,100],closeRate:[0,100],marketing:[0,1e7],fixed:[0,1e7]};
    for(const [k,[min,max]] of Object.entries(limits))if(typeof p[k]!=="number"||!Number.isFinite(p[k])||p[k]<min||p[k]>max)throw new RangeError(`Check ${k}: expected ${min} to ${max}.`);
    if(!Number.isInteger(p.visitors))throw new RangeError('Visitors must be a whole number.');
    if(p.capacity+p.acquisitionHours>48)throw new RangeError('Delivery capacity plus acquisition hours must fit within 48 hours.');
    const leads=Math.floor(p.visitors*p.leadRate/100),demand=Math.floor(leads*p.closeRate/100),slots=Math.floor(p.capacity/p.hours),orders=Math.min(demand,slots);
    const netPrice=p.price/(1+p.vat/100),netRevenuePerOrder=netPrice*(1-p.refund/100);
    // Payment fees are conservatively charged on all original sales, including refunds.
    const fee=p.price*p.feePercent/100+p.feeFixed,labor=p.hours*p.hourly;
    const contribution=netRevenuePerOrder-fee-p.delivery-labor;
    const netRevenue=orders*netRevenuePerOrder,profit=orders*contribution-p.marketing-p.fixed-p.acquisitionHours*p.hourly;
    return {leads,demand,slots,orders,unserved:Math.max(0,demand-orders),gross:orders*p.price,netRevenue,
      contribution,profit,labor:orders*labor,fees:orders*fee,cac:orders?p.marketing/orders:null,
      breakEven:contribution>0?Math.ceil((p.marketing+p.fixed+p.acquisitionHours*p.hourly)/contribution):null};
  }
  if(typeof module!=="undefined"&&module.exports)module.exports={model};else root.MonelioraLaunch={model};
})(globalThis);
