/** Shapes of the landing copy files (landings spec, decision 32). */

export type LandingApp = "cv" | "voyage"

export interface LinkCopy {
  href: string
  label: string
  /** Shown only while prices are (decision 16). */
  pricesOnly?: boolean
}

/** A link to an app's landing, resolved per host by landingHref(). */
export interface AppLinkCopy {
  app: LandingApp
  label: string
}

export interface DoorCopy {
  label: string
  note: string
  href: string
}

export interface ItemCopy {
  title: string
  text: string
}

export interface FaqItemCopy {
  q: string
  a: string
  link?: AppLinkCopy
}

export interface NavCopy {
  links: LinkCopy[]
  signIn: string
  myHome: string
  cross: AppLinkCopy
  openMenu: string
  closeMenu: string
  home: string
}

export interface HeroCopy {
  label: string
  title: string
  sub: string
  primary: DoorCopy
  secondary: DoorCopy
}

export interface AdvisorsCopy {
  label: string
  title: string
  points: string[]
  signup: LinkCopy
  signin: LinkCopy
}

export interface DataCopy {
  title: string
  points: string[]
  link: LinkCopy
}

export interface FaqCopy {
  title: string
  items: FaqItemCopy[]
}

export interface FinalCopy {
  title: string
  bridge: { text: string; link: AppLinkCopy }
}

export interface MetaCopy {
  title: string
  description: string
  ogAlt: string
}

export interface CvCopy {
  showPrices: boolean
  meta: MetaCopy
  nav: NavCopy
  hero: HeroCopy
  report: {
    title: string
    intro: string
    tiers: Record<"free" | "complet" | "premium", { name: string; tag: string }>
  }
  how: { title: string; items: ItemCopy[] }
  ways: { title: string; intro: string; items: ItemCopy[] }
  advisors: AdvisorsCopy
  prices: { title: string; intro: string; plans: { name: string; price: string; text: string }[]; note: string }
  data: DataCopy
  faq: FaqCopy
  final: FinalCopy
}

export interface VoyageCopy {
  meta: MetaCopy
  nav: NavCopy
  hero: HeroCopy & { stepsLabel: string; steps: { name: string; caption?: string }[] }
  take: { title: string; items: ItemCopy[]; note: string }
  how: { title: string; items: (ItemCopy & { link?: AppLinkCopy })[]; note: string }
  advisors: AdvisorsCopy
  data: DataCopy
  faq: FaqCopy
  final: FinalCopy
}

export interface FooterCopy {
  label: string
  tagline: string
  apps: AppLinkCopy[]
  links: LinkCopy[]
  signIn: LinkCopy
  copyright: string
}
