export function usePublicContact() {
  const publicConfig = useRuntimeConfig().public

  return {
    contactMail: String(publicConfig.contactMail || ''),
    contactPhone: String(publicConfig.contactPhone || ''),
    privacyContactPerson: String(publicConfig.privacyContactPerson || ''),
    addressName: String(publicConfig.addressName || ''),
    addressStreet: String(publicConfig.addressStreet || ''),
    addressHouseNumber: String(publicConfig.addressHouseNumber || ''),
    addressPostalCode: String(publicConfig.addressPostalCode || ''),
    addressCity: String(publicConfig.addressCity || ''),
    websiteOrigin: String(publicConfig.websiteOrigin || '')
  }
}
