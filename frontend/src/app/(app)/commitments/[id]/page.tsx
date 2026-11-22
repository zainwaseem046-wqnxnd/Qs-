"use client";

import { useParams } from "next/navigation";
import { ContractDetail } from "@/components/domain/contract-detail";

export default function CommitmentPage() {
  const { id } = useParams<{ id: string }>();
  return <ContractDetail kind="commitments" id={id} />;
}
