const paymentlines = [
  { amount: 778.00, is_igtf: false },
  { amount: 17940.57, is_igtf: true }
];
let total_with_tax = 18198.03;
let non_igtf_total = 0;
paymentlines.forEach(p => { if(!p.is_igtf) non_igtf_total += p.amount; });
let remaining_base = total_with_tax - non_igtf_total;
let igtf_amount_sum = 0;

paymentlines.forEach(p => {
  if(p.is_igtf) {
    let theoretical_base = p.amount / 1.03;
    let amount_to_pay = theoretical_base;
    if (theoretical_base > remaining_base) {
      amount_to_pay = remaining_base;
    }
    let igtf = amount_to_pay * 0.03;
    console.log("payment igtf:", igtf);
    igtf_amount_sum += igtf;
    remaining_base -= amount_to_pay;
  }
});
console.log("total igtf:", igtf_amount_sum);
let bi_igtf = igtf_amount_sum / 0.03;
console.log("bi igtf:", bi_igtf);
console.log("total due:", total_with_tax + igtf_amount_sum);
