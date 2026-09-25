import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { ErpLayout } from "./ErpLayout";
import { Partners } from "./Partners";
import { Items } from "./Items";
import { Prices } from "./Prices";
import { Accounts } from "./Accounts";
export default function ErpRoutes(){return <Routes><Route element={<ErpLayout/>}><Route index element={<Navigate to="partners" replace/>}/><Route path="partners" element={<Partners/>}/><Route path="items" element={<Items/>}/><Route path="partner-prices" element={<Prices/>}/><Route path="accounts" element={<Accounts/>}/><Route path="*" element={<NotFound/>}/></Route></Routes>;}
