import {
  Activity,
  ArrowUpRight,
  Bot,
  ClipboardList,
  ShieldCheck,
  Wrench,
} from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/baseline/avatar";
import { Button } from "@/components/baseline/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/baseline/card";
import { getOpsPilotApiBaseUrl } from "@/lib/opspilot-api";

const workspaceSections = [
  {
    icon: ClipboardList,
    title: "工单摘要",
    detail: "OP-006 后接入受控工单状态。",
  },
  {
    icon: Activity,
    title: "诊断证据",
    detail: "OP-005/007 后呈现可引用证据与假设。",
  },
  {
    icon: Wrench,
    title: "工具与审批时间线",
    detail: "OP-006 后仅显示已审计的真实调用。",
  },
  {
    icon: ShieldCheck,
    title: "恢复验证",
    detail: "OP-007 后显示验证与人工确认。",
  },
];

export default function HomePage() {
  const apiBaseUrl = getOpsPilotApiBaseUrl();

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-5 py-8 sm:px-8">
      <header className="mb-8 flex items-center justify-between border-b pb-5">
        <div className="flex items-center gap-3">
          <div className="bg-primary text-primary-foreground grid size-10 place-items-center rounded-xl">
            <Bot aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              OpsPilot 工作台
            </h1>
            <p className="text-muted-foreground text-sm">
              企业软件支持诊断与工单闭环
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="bg-muted text-muted-foreground rounded-full px-3 py-1 text-xs">
            OP-002 基线
          </span>
          <Avatar>
            <AvatarFallback>OP</AvatarFallback>
          </Avatar>
        </div>
      </header>

      <section className="grid gap-5 lg:grid-cols-[1.35fr_0.65fr]">
        <Card className="min-h-96">
          <CardHeader>
            <CardTitle>开始一次支持会话</CardTitle>
            <CardDescription>
              这是前端工作台壳，尚未连接诊断、工单或目标系统；不会伪造结果。
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col justify-between gap-8">
            <div className="border-muted-foreground/20 bg-muted/40 rounded-xl border border-dashed p-5 text-sm leading-6">
              后续会话将由 OpsPilot 自有 API 认证、保存和编排。官方 Agent Chat
              UI 仅提供已保留归属的视觉组件基线，不参与 API 转发或凭据处理。
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground text-xs">
                API 边界：{apiBaseUrl}
              </span>
              <Button
                variant="brand"
                disabled
              >
                诊断入口待 OP-007
                <ArrowUpRight aria-hidden="true" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>系统边界</CardTitle>
            <CardDescription>
              增强功能默认关闭，主流程尚未实现。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="space-y-4 text-sm">
              <div className="flex justify-between gap-4">
                <dt>Agent / LangGraph</dt>
                <dd className="text-muted-foreground">仅包边界</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt>MCP Provider</dt>
                <dd className="text-muted-foreground">未连接</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt>Skill Registry</dt>
                <dd className="text-muted-foreground">未加载</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt>Specialist</dt>
                <dd className="text-muted-foreground">未委派</dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      </section>

      <section className="mt-5 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        {workspaceSections.map(({ icon: Icon, title, detail }) => (
          <Card
            key={title}
            className="gap-3 py-5"
          >
            <CardHeader className="px-5">
              <Icon
                className="text-primary size-5"
                aria-hidden="true"
              />
              <CardTitle className="pt-2 text-base">{title}</CardTitle>
            </CardHeader>
            <CardContent className="text-muted-foreground px-5 text-sm leading-6">
              {detail}
            </CardContent>
          </Card>
        ))}
      </section>
    </main>
  );
}
