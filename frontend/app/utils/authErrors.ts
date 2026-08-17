export type AuthErrorPresentation = {
  title?: string
  message: string
  showSupportLink?: boolean
  accountStatus?: boolean
}

const AUTH_ERROR_PRESENTATIONS: Record<string, AuthErrorPresentation> = {
  ACCOUNT_SELF_DEACTIVATED: {
    title: 'Dein Konto ist deaktiviert',
    message: 'Du hast dieses Konto zuvor selbst deaktiviert. Eine Anmeldung ist derzeit nicht möglich.',
    showSupportLink: true,
    accountStatus: true
  },
  ACCOUNT_DISABLED: {
    title: 'Dieses Konto ist derzeit deaktiviert',
    message: 'Eine Anmeldung ist momentan nicht möglich.',
    showSupportLink: true,
    accountStatus: true
  },
  OAUTH_ACCESS_DENIED: { message: 'Die Anmeldung wurde abgebrochen.' },
  OAUTH_EMAIL_CONFLICT: { message: 'Zu dieser E-Mail-Adresse existiert bereits ein Konto. Melde dich zuerst mit deinem Passwort an und verknüpfe den Anbieter anschließend im Profil.' },
  OAUTH_ACCOUNT_ALREADY_LINKED: { message: 'Dieses externe Konto ist bereits mit einem anderen Benutzerkonto verbunden.' },
  OAUTH_PROVIDER_NOT_SUPPORTED: { message: 'Dieser Anmeldeanbieter wird nicht unterstützt.' },
  OAUTH_PROVIDER_DISABLED: { message: 'Dieser Anmeldeanbieter ist aktuell nicht aktiviert.' },
  INVALID_OAUTH_STATE: { message: 'Die externe Anmeldung ist abgelaufen. Bitte versuche es erneut.' },
  OAUTH_LOGIN_FAILED: { message: 'Die externe Anmeldung konnte nicht abgeschlossen werden.' },
  AUTH_REQUIRED: { message: 'Bitte melde dich zuerst an.' }
}

export function getAuthErrorPresentation(code?: string | null): AuthErrorPresentation | null {
  return code ? AUTH_ERROR_PRESENTATIONS[code] || null : null
}
