import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { ErpLayout } from "./ErpLayout";
import { Partners } from "./Partners";
import { Items } from "./Items";
import { Prices } from "./Prices";
import { Accounts } from "./Accounts";
import { Quotations } from "./Quotations";
import { SalesPlans } from "./SalesPlans";
import { SalesOrders } from "./SalesOrders";
import { ShipmentOrders } from "./ShipmentOrders";
import { Shipments } from "./Shipments";
import { SalesRecords } from "./SalesRecords";
import { TaxInvoices } from "./TaxInvoices";
import { Receivables } from "./Receivables";
import { Receipts } from "./Receipts";
import { PurchaseInvoices } from "./PurchaseInvoices";
import { PAYABLE } from "./settlement";
import { Journal } from "./Journal";
export default function ErpRoutes() {
  return (
    <Routes>
      <Route element={<ErpLayout />}>
        <Route index element={<Navigate to="quotations" replace />} />
        <Route path="quotations" element={<Quotations />} />
        <Route path="sales-plans" element={<SalesPlans />} />
        <Route path="sales-orders" element={<SalesOrders />} />
        <Route path="shipment-orders" element={<ShipmentOrders />} />
        <Route path="shipments" element={<Shipments />} />
        <Route path="sales-records" element={<SalesRecords />} />
        <Route path="tax-invoices" element={<TaxInvoices />} />
        <Route path="receivables" element={<Receivables />} />
        <Route path="receipts" element={<Receipts />} />
        <Route path="purchase-invoices" element={<PurchaseInvoices />} />
        <Route path="payables" element={<Receivables side={PAYABLE} />} />
        <Route path="payments" element={<Receipts side={PAYABLE} />} />
        <Route path="journal-preview" element={<Journal />} />
        <Route path="partners" element={<Partners />} />
        <Route path="items" element={<Items />} />
        <Route path="partner-prices" element={<Prices />} />
        <Route path="accounts" element={<Accounts />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
