import React from "react";

interface EmpiricalBadgeProps {
  text?: string;
}

export const EmpiricalBadge: React.FC<EmpiricalBadgeProps> = ({
  text = "经验默认值 · 可编辑",
}) => (
  <span
    title="该数值仅为常用经验初值，非标准数据库真值，请按实际实验仪器与条件直接修改"
    className="inline-flex items-center rounded border border-[#FDE68A] bg-[#FEF3C7] px-1.5 py-0.5 text-[10px] font-medium leading-none text-[#92400E]"
  >
    {text}
  </span>
);
