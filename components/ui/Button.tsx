import type { ComponentProps, ReactNode } from "react";
import Link from "next/link";

type Variant = "primary" | "outline";

const variants: Record<Variant, string> = {
  primary: "btn btn-primary",
  outline: "btn btn-outline",
};

type Common = {
  variant?: Variant;
  className?: string;
  children: ReactNode;
};

type ButtonAsButton = Common &
  Omit<ComponentProps<"button">, "className" | "children"> & {
    href?: undefined;
  };

type ButtonAsLink = Common & {
  href: string;
} & Omit<ComponentProps<typeof Link>, "className" | "children" | "href">;

export function Button(props: ButtonAsButton | ButtonAsLink) {
  const { variant = "primary", className = "", children } = props;
  const classes = `${variants[variant]} ${className}`.trim();

  if ("href" in props && props.href) {
    const { href, variant: _v, className: _c, children: _ch, ...rest } = props;
    return (
      <Link href={href} className={classes} {...rest}>
        {children}
      </Link>
    );
  }

  const { variant: _v, className: _c, children: _ch, ...rest } =
    props as ButtonAsButton;
  return (
    <button type="button" className={classes} {...rest}>
      {children}
    </button>
  );
}
