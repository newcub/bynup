# builder/management/commands/load_color_palettes.py

from django.core.management.base import BaseCommand
from builder.models import ColorPalette, ColorPaletteColor

class Command(BaseCommand):
    help = 'Load 100+ professional color palettes from ModernEcommerce collection'

    def handle(self, *args, **options):
        self.stdout.write('🔄 Loading ModernEcommerce color palettes...')
        
        palettes = self.get_palette_data()
        valid_count = 0

        for palette_data in palettes:
            # Generate slug from name
            slug = palette_data['name'].lower().replace(' ', '-').replace('&', 'and').replace("'", "").replace('(', '').replace(')', '')
            slug = ''.join(c for c in slug if c.isalnum() or c == '-')
            slug = slug.strip('-')
            
            palette, created = ColorPalette.objects.get_or_create(
                name=palette_data['name'],
                defaults={
                    'category': palette_data['category'],
                    'mood': palette_data['mood'],
                    'slug': slug,
                    'is_active': True,
                }
            )

            if created:
                for order, (color_type, name, var_name, hex_val, rgb_val) in enumerate(palette_data['colors']):
                    ColorPaletteColor.objects.get_or_create(
                        palette=palette,
                        variable_name=var_name.lstrip('--'),
                        defaults={
                            'name': name,
                            'color_type': color_type,
                            'hex_value': hex_val,
                            'rgb_value': rgb_val,
                            'display_order': order,
                        }
                    )
                valid_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {palette.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'• Skipped (exists): {palette.name}'))

        self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully loaded {valid_count} professional palettes!'))

    def get_palette_data(self):
        return [
            # ============================================
            # MODERNECOMMERCE5
            # ============================================
            {
                'name': 'ModernEcommerce5 - Lavender Gray',
                'category': 'ModernEcommerce5',
                'mood': 'cool',
                'colors': [
                    ('background', 'Lavender Gray', '--background', '#E6E8F5', '230, 232, 245'),
                    ('text', 'Deep Charcoal', '--text', '#2A2A34', '42, 42, 52'),
                    ('heading', 'Teal Blue', '--heading', '#5596AA', '85, 150, 170'),
                    ('primary', 'Soft Blue Gray', '--primary', '#AABFD4', '170, 191, 212'),
                    ('secondary', 'Lavender Gray', '--secondary', '#E6E8F5', '230, 232, 245'),
                    ('accent', 'Teal Blue', '--accent', '#5596AA', '85, 150, 170'),
                    ('border', 'Subtle Border', '--border', 'rgba(42,42,52,0.1)', '42, 42, 52, 0.1'),
                    ('success', 'Soft Lavender', '--success', '#DCD7DD', '220, 215, 221'),
                    ('warning', 'Deep Charcoal', '--warning', '#2A2A34', '42, 42, 52'),
                ]
            },
            {
                'name': 'ModernEcommerce5 - Warm Amber',
                'category': 'ModernEcommerce5',
                'mood': 'warm',
                'colors': [
                    ('background', 'Warm Ivory', '--background', '#FCF8F0', '252, 248, 240'),
                    ('text', 'Very Dark Brown', '--text', '#1A1612', '26, 22, 18'),
                    ('heading', 'Warm Amber', '--heading', '#B86A3A', '184, 106, 58'),
                    ('primary', 'Soft Warm Beige', '--primary', '#D4B08A', '212, 176, 138'),
                    ('secondary', 'Warm Cream', '--secondary', '#F8F0E8', '248, 240, 232'),
                    ('accent', 'Warm Amber', '--accent', '#B86A3A', '184, 106, 58'),
                    ('border', 'Subtle Border', '--border', 'rgba(26,22,18,0.1)', '26, 22, 18, 0.1'),
                    ('success', 'Soft Green', '--success', '#6B8C5A', '107, 140, 90'),
                    ('warning', 'Golden', '--warning', '#D4A03A', '212, 160, 58'),
                ]
            },
            {
                'name': 'ModernEcommerce5 - Sage Green',
                'category': 'ModernEcommerce5',
                'mood': 'natural',
                'colors': [
                    ('background', 'Sage Cream', '--background', '#F0F4EC', '240, 244, 236'),
                    ('text', 'Deep Sage', '--text', '#1A2A1E', '26, 42, 30'),
                    ('heading', 'Soft Sage Green', '--heading', '#5A8A6A', '90, 138, 106'),
                    ('primary', 'Soft Sage', '--primary', '#A8C0A8', '168, 192, 168'),
                    ('secondary', 'Sage Cream', '--secondary', '#F0F4EC', '240, 244, 236'),
                    ('accent', 'Sage Green', '--accent', '#5A8A6A', '90, 138, 106'),
                    ('border', 'Subtle Border', '--border', 'rgba(26,42,30,0.1)', '26, 42, 30, 0.1'),
                    ('success', 'Deep Green', '--success', '#4A7A5A', '74, 122, 90'),
                    ('warning', 'Golden', '--warning', '#C9A84A', '201, 168, 74'),
                ]
            },
            {
                'name': 'ModernEcommerce5 - Dusty Rose',
                'category': 'ModernEcommerce5',
                'mood': 'warm',
                'colors': [
                    ('background', 'Dusty Rose', '--background', '#F8F0F0', '248, 240, 240'),
                    ('text', 'Deep Warm Charcoal', '--text', '#2A2020', '42, 32, 32'),
                    ('heading', 'Soft Dusty Rose', '--heading', '#B86A7A', '184, 106, 122'),
                    ('primary', 'Soft Rose', '--primary', '#D4B0B8', '212, 176, 184'),
                    ('secondary', 'Dusty Rose', '--secondary', '#F8F0F0', '248, 240, 240'),
                    ('accent', 'Dusty Rose', '--accent', '#B86A7A', '184, 106, 122'),
                    ('border', 'Subtle Border', '--border', 'rgba(42,32,32,0.1)', '42, 32, 32, 0.1'),
                    ('success', 'Soft Green', '--success', '#6B8C5A', '107, 140, 90'),
                    ('warning', 'Golden', '--warning', '#C9A84A', '201, 168, 74'),
                ]
            },
            {
                'name': 'ModernEcommerce5 - Gold',
                'category': 'ModernEcommerce5',
                'mood': 'luxurious',
                'colors': [
                    ('background', 'Warm Parchment', '--background', '#F5F0E8', '245, 240, 232'),
                    ('text', 'Pure Black', '--text', '#0D0D0D', '13, 13, 13'),
                    ('heading', 'Gold', '--heading', '#D4AF37', '212, 175, 55'),
                    ('primary', 'Soft Gold Beige', '--primary', '#B8A88A', '184, 168, 138'),
                    ('secondary', 'Warm Parchment', '--secondary', '#F5F0E8', '245, 240, 232'),
                    ('accent', 'Gold', '--accent', '#D4AF37', '212, 175, 55'),
                    ('border', 'Subtle Border', '--border', 'rgba(13,13,13,0.1)', '13, 13, 13, 0.1'),
                    ('success', 'Soft Green', '--success', '#6B8C5A', '107, 140, 90'),
                    ('warning', 'Golden', '--warning', '#C9A84A', '201, 168, 74'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE6
            # ============================================
            {
                'name': 'ModernEcommerce6 - Teal Green',
                'category': 'ModernEcommerce6',
                'mood': 'cool',
                'colors': [
                    ('background', 'Light Gray', '--background', '#f8f9fa', '248, 249, 250'),
                    ('border', 'White', '--border', '#ffffff', '255, 255, 255'),
                    ('secondary', 'Dark Gray', '--secondary', '#333333', '51, 51, 51'),
                    ('success', 'Dark Gray', '--success', '#222222', '34, 34, 34'),
                    ('text', 'Teal Green', '--text', '#4D8581', '77, 133, 129'),
                    ('primary', 'Warm Beige', '--primary', '#B0988B', '176, 152, 139'),
                    ('heading', 'Light Teal', '--heading', '#ABDED7', '171, 222, 215'),
                    ('accent', 'Light Gray', '--accent', '#e9ecef', '233, 236, 239'),
                    ('error', 'Soft Red', '--error', '#AA5555', '170, 85, 85'),
                ]
            },
            {
                'name': 'ModernEcommerce6 - Bold Blue',
                'category': 'ModernEcommerce6',
                'mood': 'professional',
                'colors': [
                    ('background', 'Cool Light Gray', '--background', '#F5F7FA', '245, 247, 250'),
                    ('border', 'White', '--border', '#ffffff', '255, 255, 255'),
                    ('secondary', 'Deep Navy', '--secondary', '#1A2A3A', '26, 42, 58'),
                    ('success', 'Very Dark Navy', '--success', '#0D1B2A', '13, 27, 42'),
                    ('text', 'Bold Blue', '--text', '#2563EB', '37, 99, 235'),
                    ('primary', 'Soft Blue', '--primary', '#93B4E8', '147, 180, 232'),
                    ('heading', 'Light Blue', '--heading', '#60A5FA', '96, 165, 250'),
                    ('accent', 'Light Gray', '--accent', '#e2e8f0', '226, 232, 240'),
                    ('error', 'Bold Red', '--error', '#DC2626', '220, 38, 38'),
                ]
            },
            {
                'name': 'ModernEcommerce6 - Gold',
                'category': 'ModernEcommerce6',
                'mood': 'luxurious',
                'colors': [
                    ('background', 'Warm Parchment', '--background', '#F5F0E8', '245, 240, 232'),
                    ('border', 'Warm White', '--border', '#FCF8F0', '252, 248, 240'),
                    ('secondary', 'Pure Black', '--secondary', '#0D0D0D', '13, 13, 13'),
                    ('success', 'Near Black', '--success', '#1A1A1A', '26, 26, 26'),
                    ('text', 'Gold', '--text', '#D4AF37', '212, 175, 55'),
                    ('primary', 'Soft Gold Beige', '--primary', '#B8A88A', '184, 168, 138'),
                    ('heading', 'Light Gold', '--heading', '#E8D5B5', '232, 213, 181'),
                    ('accent', 'Warm Gray', '--accent', '#e8e0d8', '232, 224, 216'),
                    ('error', 'Soft Red', '--error', '#AA5555', '170, 85, 85'),
                ]
            },
            {
                'name': 'ModernEcommerce6 - Vibrant Orange',
                'category': 'ModernEcommerce6',
                'mood': 'energetic',
                'colors': [
                    ('background', 'Warm Light', '--background', '#F8F4F0', '248, 244, 240'),
                    ('border', 'White', '--border', '#ffffff', '255, 255, 255'),
                    ('secondary', 'Very Dark Brown', '--secondary', '#1A1410', '26, 20, 16'),
                    ('success', 'Almost Black', '--success', '#0D0A08', '13, 10, 8'),
                    ('text', 'Vibrant Orange', '--text', '#E85A2A', '232, 90, 42'),
                    ('primary', 'Soft Orange', '--primary', '#F0A080', '240, 160, 128'),
                    ('heading', 'Light Orange', '--heading', '#F5C8B0', '245, 200, 176'),
                    ('accent', 'Warm Gray', '--accent', '#e8e0d8', '232, 224, 216'),
                    ('error', 'Bold Red', '--error', '#DC2626', '220, 38, 38'),
                ]
            },
            {
                'name': 'ModernEcommerce6 - Sage Green',
                'category': 'ModernEcommerce6',
                'mood': 'natural',
                'colors': [
                    ('background', 'Sage Cream', '--background', '#F0F4EC', '240, 244, 236'),
                    ('border', 'Off White', '--border', '#F8FAF5', '248, 250, 245'),
                    ('secondary', 'Deep Sage', '--secondary', '#1A2A1E', '26, 42, 30'),
                    ('success', 'Very Dark Sage', '--success', '#0D1A10', '13, 26, 16'),
                    ('text', 'Sage Green', '--text', '#4A7A5A', '74, 122, 90'),
                    ('primary', 'Soft Sage', '--primary', '#8AA88A', '138, 168, 138'),
                    ('heading', 'Light Sage', '--heading', '#A8C8A8', '168, 200, 168'),
                    ('accent', 'Sage Gray', '--accent', '#dce4d8', '220, 228, 216'),
                    ('error', 'Soft Red', '--error', '#AA5555', '170, 85, 85'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE7
            # ============================================
            {
                'name': 'ModernEcommerce7 - Navy Burgundy',
                'category': 'ModernEcommerce7',
                'mood': 'professional',
                'colors': [
                    ('primary', 'Light Blue Gray', '--primary', '#F6FAFD', '246, 250, 253'),
                    ('text', 'Deep Navy', '--text', '#1A3D63', '26, 61, 99'),
                    ('heading', 'Deep Burgundy', '--heading', '#6A1931', '106, 25, 49'),
                    ('background', 'Medium Blue', '--background', '#4A7FA7', '74, 127, 167'),
                    ('accent', 'Soft Blue', '--accent', '#B3CFE5', '179, 207, 229'),
                ]
            },
            {
                'name': 'ModernEcommerce7 - Dusty Rose',
                'category': 'ModernEcommerce7',
                'mood': 'warm',
                'colors': [
                    ('primary', 'Soft Pink White', '--primary', '#FDF8F8', '253, 248, 248'),
                    ('text', 'Deep Plum Slate', '--text', '#2A2030', '42, 32, 48'),
                    ('heading', 'Soft Dusty Rose', '--heading', '#B86A7A', '184, 106, 122'),
                    ('background', 'Soft Rose', '--background', '#D4B0B8', '212, 176, 184'),
                    ('accent', 'Light Rose', '--accent', '#F0E4E8', '240, 228, 232'),
                ]
            },
            {
                'name': 'ModernEcommerce7 - Forest Gold',
                'category': 'ModernEcommerce7',
                'mood': 'natural',
                'colors': [
                    ('primary', 'Mint Cream', '--primary', '#F8FCF5', '248, 252, 245'),
                    ('text', 'Deep Forest', '--text', '#1A2A1A', '26, 42, 26'),
                    ('heading', 'Warm Gold', '--heading', '#B8963A', '184, 150, 58'),
                    ('background', 'Soft Emerald', '--background', '#5A8A5A', '90, 138, 90'),
                    ('accent', 'Light Sage', '--accent', '#D4E8D0', '212, 232, 208'),
                ]
            },
            {
                'name': 'ModernEcommerce7 - Warm Amber',
                'category': 'ModernEcommerce7',
                'mood': 'warm',
                'colors': [
                    ('primary', 'Warm Ivory', '--primary', '#FCF8F0', '252, 248, 240'),
                    ('text', 'Very Dark Brown', '--text', '#1A1612', '26, 22, 18'),
                    ('heading', 'Warm Amber', '--heading', '#B86A3A', '184, 106, 58'),
                    ('background', 'Soft Terracotta', '--background', '#D4A080', '212, 160, 128'),
                    ('accent', 'Light Warm', '--accent', '#F0E4D8', '240, 228, 216'),
                ]
            },
            {
                'name': 'ModernEcommerce7 - Lavender Purple',
                'category': 'ModernEcommerce7',
                'mood': 'elegant',
                'colors': [
                    ('primary', 'Lavender Cream', '--primary', '#F8F6FC', '248, 246, 252'),
                    ('text', 'Deep Lavender', '--text', '#2A2440', '42, 36, 64'),
                    ('heading', 'Soft Lavender Purple', '--heading', '#8A7AB8', '138, 122, 184'),
                    ('background', 'Light Lavender', '--background', '#B8A8D4', '184, 168, 212'),
                    ('accent', 'Very Light Lavender', '--accent', '#E4DCF0', '228, 220, 240'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE8
            # ============================================
            {
                'name': 'ModernEcommerce8 - Rose Pink',
                'category': 'ModernEcommerce8',
                'mood': 'warm',
                'colors': [
                    ('accent', 'Soft Blush White', '--accent', '#FDF9FB', '253, 249, 251'),
                    ('border', 'Dark Charcoal', '--border', '#333333', '51, 51, 51'),
                    ('primary', 'Deep Rose Pink', '--primary', '#A55166', '165, 81, 102'),
                    ('heading', 'Soft Rose', '--heading', '#D38C9D', '211, 140, 157'),
                    ('background', 'Light Rose', '--background', '#E2B4C1', '226, 180, 193'),
                    ('text', 'Very Light Pink', '--text', '#F7DAE7', '247, 218, 231'),
                    ('secondary', 'White', '--secondary', '#FFFFFF', '255, 255, 255'),
                    ('success', 'Gray', '--success', '#666666', '102, 102, 102'),
                ]
            },
            {
                'name': 'ModernEcommerce8 - Coastal Teal',
                'category': 'ModernEcommerce8',
                'mood': 'cool',
                'colors': [
                    ('accent', 'Coastal Cream', '--accent', '#F5F8FA', '245, 248, 250'),
                    ('border', 'Deep Navy', '--border', '#1A2A3A', '26, 42, 58'),
                    ('primary', 'Soft Teal', '--primary', '#5A8A8A', '90, 138, 138'),
                    ('heading', 'Light Teal', '--heading', '#8AB8B8', '138, 184, 184'),
                    ('background', 'Light Coastal', '--background', '#D0E0E0', '208, 224, 224'),
                    ('text', 'Very Light Teal', '--text', '#E8F0F0', '232, 240, 240'),
                    ('secondary', 'White', '--secondary', '#FFFFFF', '255, 255, 255'),
                    ('success', 'Muted Teal', '--success', '#7A8A8A', '122, 138, 138'),
                ]
            },
            {
                'name': 'ModernEcommerce8 - Warm Amber',
                'category': 'ModernEcommerce8',
                'mood': 'warm',
                'colors': [
                    ('accent', 'Warm Ivory', '--accent', '#FCF8F0', '252, 248, 240'),
                    ('border', 'Very Dark Brown', '--border', '#1A1612', '26, 22, 18'),
                    ('primary', 'Warm Amber', '--primary', '#B86A3A', '184, 106, 58'),
                    ('heading', 'Soft Terracotta', '--heading', '#D4A080', '212, 160, 128'),
                    ('background', 'Warm Beige', '--background', '#F0E4D8', '240, 228, 216'),
                    ('text', 'Very Light Warm', '--text', '#F8F0E8', '248, 240, 232'),
                    ('secondary', 'White', '--secondary', '#FFFFFF', '255, 255, 255'),
                    ('success', 'Muted Warm', '--success', '#8A7A6A', '138, 122, 106'),
                ]
            },
            {
                'name': 'ModernEcommerce8 - Lavender',
                'category': 'ModernEcommerce8',
                'mood': 'elegant',
                'colors': [
                    ('accent', 'Lavender Cream', '--accent', '#F8F6FC', '248, 246, 252'),
                    ('border', 'Deep Lavender', '--border', '#2A2440', '42, 36, 64'),
                    ('primary', 'Soft Lavender Purple', '--primary', '#8A7AB8', '138, 122, 184'),
                    ('heading', 'Light Lavender', '--heading', '#B8A8D4', '184, 168, 212'),
                    ('background', 'Very Light Lavender', '--background', '#E4DCF0', '228, 220, 240'),
                    ('text', 'Light Lavender', '--text', '#F0ECF8', '240, 236, 248'),
                    ('secondary', 'White', '--secondary', '#FFFFFF', '255, 255, 255'),
                    ('success', 'Muted Lavender', '--success', '#9A8AB0', '154, 138, 176'),
                ]
            },
            {
                'name': 'ModernEcommerce8 - Sage Gold',
                'category': 'ModernEcommerce8',
                'mood': 'natural',
                'colors': [
                    ('accent', 'Mint Cream', '--accent', '#F5F8F2', '245, 248, 242'),
                    ('border', 'Deep Forest', '--border', '#1A2A1A', '26, 42, 26'),
                    ('primary', 'Warm Gold', '--primary', '#B8963A', '184, 150, 58'),
                    ('heading', 'Soft Gold', '--heading', '#D4B86A', '212, 184, 106'),
                    ('background', 'Light Sage', '--background', '#E0E8D8', '224, 232, 216'),
                    ('text', 'Very Light Sage', '--text', '#F0F4E8', '240, 244, 232'),
                    ('secondary', 'White', '--secondary', '#FFFFFF', '255, 255, 255'),
                    ('success', 'Muted Sage', '--success', '#7A8A6A', '122, 138, 106'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE9
            # ============================================
            {
                'name': 'ModernEcommerce9 - Olive Sage',
                'category': 'ModernEcommerce9',
                'mood': 'natural',
                'colors': [
                    ('success', 'White', '--success', '#ffffff', '255, 255, 255'),
                    ('accent', 'Dark Charcoal', '--accent', '#333333', '51, 51, 51'),
                    ('secondary', 'Sage Olive Green', '--secondary', '#58784F', '88, 120, 79'),
                    ('primary', 'Soft Sage', '--primary', '#709078', '112, 144, 120'),
                    ('heading', 'Teal Sage', '--heading', '#77B09F', '119, 176, 159'),
                    ('text', 'Warm Peach', '--text', '#F8CFAF', '248, 207, 175'),
                    ('border', 'Medium Gray', '--border', '#555555', '85, 85, 85'),
                    ('background', 'Light Gray', '--background', '#f9f9f9', '249, 249, 249'),
                ]
            },
            {
                'name': 'ModernEcommerce9 - Dusty Rose',
                'category': 'ModernEcommerce9',
                'mood': 'warm',
                'colors': [
                    ('success', 'White', '--success', '#ffffff', '255, 255, 255'),
                    ('accent', 'Deep Plum Slate', '--accent', '#2A2028', '42, 32, 40'),
                    ('secondary', 'Soft Dusty Rose', '--secondary', '#B86A7A', '184, 106, 122'),
                    ('primary', 'Soft Rose', '--primary', '#D4B0B8', '212, 176, 184'),
                    ('heading', 'Light Rose', '--heading', '#D48A9A', '212, 138, 154'),
                    ('text', 'Very Light Rose', '--text', '#F8E8EC', '248, 232, 236'),
                    ('border', 'Muted Rose', '--border', '#8A7A80', '138, 122, 128'),
                    ('background', 'Light Rose', '--background', '#f9f5f6', '249, 245, 246'),
                ]
            },
            {
                'name': 'ModernEcommerce9 - Coastal Teal',
                'category': 'ModernEcommerce9',
                'mood': 'cool',
                'colors': [
                    ('success', 'White', '--success', '#ffffff', '255, 255, 255'),
                    ('accent', 'Deep Navy', '--accent', '#1A2A3A', '26, 42, 58'),
                    ('secondary', 'Soft Teal', '--secondary', '#5A8A8A', '90, 138, 138'),
                    ('primary', 'Light Teal', '--primary', '#8AB8B8', '138, 184, 184'),
                    ('heading', 'Medium Teal', '--heading', '#7AA8A8', '122, 168, 168'),
                    ('text', 'Light Coastal', '--text', '#E8F0F0', '232, 240, 240'),
                    ('border', 'Muted Teal', '--border', '#7A8A8A', '122, 138, 138'),
                    ('background', 'Light Coastal', '--background', '#f5f8f8', '245, 248, 248'),
                ]
            },
            {
                'name': 'ModernEcommerce9 - Warm Amber',
                'category': 'ModernEcommerce9',
                'mood': 'warm',
                'colors': [
                    ('success', 'White', '--success', '#ffffff', '255, 255, 255'),
                    ('accent', 'Very Dark Brown', '--accent', '#1A1612', '26, 22, 18'),
                    ('secondary', 'Warm Amber', '--secondary', '#B86A3A', '184, 106, 58'),
                    ('primary', 'Soft Terracotta', '--primary', '#D4A080', '212, 160, 128'),
                    ('heading', 'Medium Terracotta', '--heading', '#C49070', '196, 144, 112'),
                    ('text', 'Warm Ivory', '--text', '#F8F0E8', '248, 240, 232'),
                    ('border', 'Muted Warm', '--border', '#8A7A6A', '138, 122, 106'),
                    ('background', 'Warm Cream', '--background', '#fcf8f0', '252, 248, 240'),
                ]
            },
            {
                'name': 'ModernEcommerce9 - Gold',
                'category': 'ModernEcommerce9',
                'mood': 'luxurious',
                'colors': [
                    ('success', 'White', '--success', '#ffffff', '255, 255, 255'),
                    ('accent', 'Pure Black', '--accent', '#0D0D0D', '13, 13, 13'),
                    ('secondary', 'Gold', '--secondary', '#D4AF37', '212, 175, 55'),
                    ('primary', 'Soft Gold', '--primary', '#C9A96E', '201, 169, 110'),
                    ('heading', 'Light Gold', '--heading', '#E8D5B5', '232, 213, 181'),
                    ('text', 'Warm Ivory', '--text', '#F8F0E8', '248, 240, 232'),
                    ('border', 'Muted Taupe', '--border', '#8A8278', '138, 130, 120'),
                    ('background', 'Warm Cream', '--background', '#fcf8f0', '252, 248, 240'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE11
            # ============================================
            {
                'name': 'ModernEcommerce11 - Warm Beige Teal',
                'category': 'ModernEcommerce11',
                'mood': 'warm',
                'colors': [
                    ('secondary', 'Warm Beige Cream', '--secondary', '#EEE7DF', '238, 231, 223'),
                    ('accent', 'Dark Charcoal', '--accent', '#333333', '51, 51, 51'),
                    ('heading', 'Teal Sage', '--heading', '#4D8581', '77, 133, 129'),
                    ('text', 'Warm Beige Brown', '--text', '#B0988B', '176, 152, 139'),
                    ('primary', 'Light Teal', '--primary', '#ABDED7', '171, 222, 215'),
                    ('background', 'Warm Beige', '--background', '#DBCBBE', '219, 203, 190'),
                    ('border', 'Medium Gray', '--border', '#555555', '85, 85, 85'),
                    ('success', 'White', '--success', '#FFFFFF', '255, 255, 255'),
                ]
            },
            {
                'name': 'ModernEcommerce11 - Rose Cream',
                'category': 'ModernEcommerce11',
                'mood': 'warm',
                'colors': [
                    ('secondary', 'Rose Cream', '--secondary', '#FDF8F5', '253, 248, 245'),
                    ('accent', 'Deep Plum', '--accent', '#2A2028', '42, 32, 40'),
                    ('heading', 'Soft Dusty Rose', '--heading', '#B86A7A', '184, 106, 122'),
                    ('text', 'Light Rose', '--text', '#D4A8B0', '212, 168, 176'),
                    ('primary', 'Very Light Rose', '--primary', '#E8D0D8', '232, 208, 216'),
                    ('background', 'Soft Rose', '--background', '#F5E8EC', '245, 232, 236'),
                    ('border', 'Muted Rose', '--border', '#8A7A80', '138, 122, 128'),
                    ('success', 'White', '--success', '#FFFFFF', '255, 255, 255'),
                ]
            },
            {
                'name': 'ModernEcommerce11 - Sage Green',
                'category': 'ModernEcommerce11',
                'mood': 'natural',
                'colors': [
                    ('secondary', 'Sage Cream', '--secondary', '#F5F8F5', '245, 248, 245'),
                    ('accent', 'Deep Sage', '--accent', '#1A2A1E', '26, 42, 30'),
                    ('heading', 'Soft Sage Green', '--heading', '#5A8A6A', '90, 138, 106'),
                    ('text', 'Light Sage', '--text', '#A8C0A8', '168, 192, 168'),
                    ('primary', 'Very Light Sage', '--primary', '#D0E4D0', '208, 228, 208'),
                    ('background', 'Light Sage', '--background', '#E8F0E8', '232, 240, 232'),
                    ('border', 'Muted Sage', '--border', '#6A7A6A', '106, 122, 106'),
                    ('success', 'White', '--success', '#FFFFFF', '255, 255, 255'),
                ]
            },
            {
                'name': 'ModernEcommerce11 - Warm Amber',
                'category': 'ModernEcommerce11',
                'mood': 'warm',
                'colors': [
                    ('secondary', 'Warm Ivory', '--secondary', '#FCF8F0', '252, 248, 240'),
                    ('accent', 'Very Dark Brown', '--accent', '#1A1612', '26, 22, 18'),
                    ('heading', 'Warm Amber', '--heading', '#B86A3A', '184, 106, 58'),
                    ('text', 'Soft Terracotta', '--text', '#D4A080', '212, 160, 128'),
                    ('primary', 'Warm Beige', '--primary', '#F0E4D8', '240, 228, 216'),
                    ('background', 'Warm Cream', '--background', '#F8F0E8', '248, 240, 232'),
                    ('border', 'Muted Warm', '--border', '#8A7A6A', '138, 122, 106'),
                    ('success', 'White', '--success', '#FFFFFF', '255, 255, 255'),
                ]
            },
            {
                'name': 'ModernEcommerce11 - Lavender',
                'category': 'ModernEcommerce11',
                'mood': 'elegant',
                'colors': [
                    ('secondary', 'Lavender Cream', '--secondary', '#F8F6FC', '248, 246, 252'),
                    ('accent', 'Deep Lavender', '--accent', '#2A2440', '42, 36, 64'),
                    ('heading', 'Soft Lavender Purple', '--heading', '#8A7AB8', '138, 122, 184'),
                    ('text', 'Light Lavender', '--text', '#B8A8D4', '184, 168, 212'),
                    ('primary', 'Very Light Lavender', '--primary', '#E4DCF0', '228, 220, 240'),
                    ('background', 'Light Lavender', '--background', '#F0E8F5', '240, 232, 245'),
                    ('border', 'Muted Lavender', '--border', '#9A8AB0', '154, 138, 176'),
                    ('success', 'White', '--success', '#FFFFFF', '255, 255, 255'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE12
            # ============================================
            {
                'name': 'ModernEcommerce12 - Olive Gold',
                'category': 'ModernEcommerce12',
                'mood': 'warm',
                'colors': [
                    ('secondary', 'Warm Cream', '--secondary', '#f9f6f2', '249, 246, 242'),
                    ('accent', 'Dark Charcoal', '--accent', '#333333', '51, 51, 51'),
                    ('heading', 'Olive Green', '--heading', '#626616', '98, 102, 22'),
                    ('text', 'Warm Beige Gold', '--text', '#e2a970', '226, 169, 112'),
                    ('background', 'Warm Gold', '--background', '#f1bb71', '241, 187, 113'),
                    ('accent2', 'Light Gray', '--accent2', '#e5e5e5', '229, 229, 229'),
                    ('primary', 'White', '--primary', '#ffffff', '255, 255, 255'),
                    ('border', 'Dark', '--border', '#1a1a1a', '26, 26, 26'),
                    ('success', 'Light Gray', '--success', '#f8f8f8', '248, 248, 248'),
                    ('error', 'Medium Gray', '--error', '#999999', '153, 153, 153'),
                ]
            },
            {
                'name': 'ModernEcommerce12 - Rose Cream',
                'category': 'ModernEcommerce12',
                'mood': 'warm',
                'colors': [
                    ('secondary', 'Rose Cream', '--secondary', '#FDF8F5', '253, 248, 245'),
                    ('accent', 'Deep Plum', '--accent', '#2A2028', '42, 32, 40'),
                    ('heading', 'Soft Dusty Rose', '--heading', '#B86A7A', '184, 106, 122'),
                    ('text', 'Light Rose', '--text', '#D4A8B0', '212, 168, 176'),
                    ('background', 'Very Light Rose', '--background', '#E8D0D8', '232, 208, 216'),
                    ('accent2', 'Soft Rose Gray', '--accent2', '#e8dce0', '232, 220, 224'),
                    ('primary', 'White', '--primary', '#ffffff', '255, 255, 255'),
                    ('border', 'Deep Plum', '--border', '#2A2028', '42, 32, 40'),
                    ('success', 'Light Rose', '--success', '#f8f5f6', '248, 245, 246'),
                    ('error', 'Muted Rose', '--error', '#999090', '153, 144, 144'),
                ]
            },
            {
                'name': 'ModernEcommerce12 - Platinum Gray',
                'category': 'ModernEcommerce12',
                'mood': 'modern',
                'colors': [
                    ('secondary', 'Cool Cream', '--secondary', '#F5F5F0', '245, 245, 240'),
                    ('accent', 'Very Dark Navy', '--accent', '#0D0D1A', '13, 13, 26'),
                    ('heading', 'Muted Platinum Blue', '--heading', '#6A7A8A', '106, 122, 138'),
                    ('text', 'Soft Platinum', '--text', '#9A9AAA', '154, 154, 170'),
                    ('background', 'Cool Gray', '--background', '#C0C8D0', '192, 200, 208'),
                    ('accent2', 'Light Gray', '--accent2', '#d8dce0', '216, 220, 224'),
                    ('primary', 'White', '--primary', '#ffffff', '255, 255, 255'),
                    ('border', 'Dark Navy', '--border', '#0D0D1A', '13, 13, 26'),
                    ('success', 'Light Gray', '--success', '#f0f0f0', '240, 240, 240'),
                    ('error', 'Medium Gray', '--error', '#888890', '136, 136, 144'),
                ]
            },
            {
                'name': 'ModernEcommerce12 - Warm Amber',
                'category': 'ModernEcommerce12',
                'mood': 'warm',
                'colors': [
                    ('secondary', 'Warm Ivory', '--secondary', '#FCF8F0', '252, 248, 240'),
                    ('accent', 'Very Dark Brown', '--accent', '#1A1612', '26, 22, 18'),
                    ('heading', 'Warm Amber', '--heading', '#B86A3A', '184, 106, 58'),
                    ('text', 'Soft Terracotta', '--text', '#D4A080', '212, 160, 128'),
                    ('background', 'Warm Beige', '--background', '#F0E4D8', '240, 228, 216'),
                    ('accent2', 'Warm Gray', '--accent2', '#e8dcd0', '232, 220, 208'),
                    ('primary', 'White', '--primary', '#ffffff', '255, 255, 255'),
                    ('border', 'Dark Brown', '--border', '#1A1612', '26, 22, 18'),
                    ('success', 'Warm Light', '--success', '#f8f0e8', '248, 240, 232'),
                    ('error', 'Muted Warm', '--error', '#8A7A6A', '138, 122, 106'),
                ]
            },
            {
                'name': 'ModernEcommerce12 - Lavender',
                'category': 'ModernEcommerce12',
                'mood': 'elegant',
                'colors': [
                    ('secondary', 'Lavender Cream', '--secondary', '#F8F6FC', '248, 246, 252'),
                    ('accent', 'Deep Lavender', '--accent', '#2A2440', '42, 36, 64'),
                    ('heading', 'Soft Lavender Purple', '--heading', '#8A7AB8', '138, 122, 184'),
                    ('text', 'Light Lavender', '--text', '#B8A8D4', '184, 168, 212'),
                    ('background', 'Very Light Lavender', '--background', '#E4DCF0', '228, 220, 240'),
                    ('accent2', 'Lavender Gray', '--accent2', '#e0d8e8', '224, 216, 232'),
                    ('primary', 'White', '--primary', '#ffffff', '255, 255, 255'),
                    ('border', 'Deep Lavender', '--border', '#2A2440', '42, 36, 64'),
                    ('success', 'Light Lavender', '--success', '#f5f0f8', '245, 240, 248'),
                    ('error', 'Muted Lavender', '--error', '#9A8AB0', '154, 138, 176'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE16
            # ============================================
            {
                'name': 'ModernEcommerce16 - Plum Mauve',
                'category': 'ModernEcommerce16',
                'mood': 'elegant',
                'colors': [
                    ('text', 'Soft Cream', '--text', '#FAEEE9', '250, 238, 233'),
                    ('primary', 'Warm Plum Mauve', '--primary', '#735366', '115, 83, 102'),
                    ('heading', 'Soft Lavender Mauve', '--heading', '#A77A95', '167, 122, 149'),
                    ('background', 'Warm Gold', '--background', '#F5D69B', '245, 214, 155'),
                    ('border', 'Lavender Gray', '--border', '#C3C3D5', '195, 195, 213'),
                ]
            },
            {
                'name': 'ModernEcommerce16 - Dusty Rose',
                'category': 'ModernEcommerce16',
                'mood': 'warm',
                'colors': [
                    ('text', 'Rose Cream', '--text', '#FDF8F5', '253, 248, 245'),
                    ('primary', 'Soft Dusty Rose', '--primary', '#B86A7A', '184, 106, 122'),
                    ('heading', 'Light Rose', '--heading', '#D4A8B0', '212, 168, 176'),
                    ('background', 'Very Light Rose', '--background', '#E8D0D8', '232, 208, 216'),
                    ('border', 'Rose Gray', '--border', '#e0d0d8', '224, 208, 216'),
                ]
            },
            {
                'name': 'ModernEcommerce16 - Sage Green',
                'category': 'ModernEcommerce16',
                'mood': 'natural',
                'colors': [
                    ('text', 'Sage Cream', '--text', '#F5F8F5', '245, 248, 245'),
                    ('primary', 'Soft Sage Green', '--primary', '#5A8A6A', '90, 138, 106'),
                    ('heading', 'Light Sage', '--heading', '#A8C0A8', '168, 192, 168'),
                    ('background', 'Very Light Sage', '--background', '#D0E4D0', '208, 228, 208'),
                    ('border', 'Sage Gray', '--border', '#d0dcd0', '208, 220, 208'),
                ]
            },
            {
                'name': 'ModernEcommerce16 - Warm Amber',
                'category': 'ModernEcommerce16',
                'mood': 'warm',
                'colors': [
                    ('text', 'Warm Ivory', '--text', '#FCF8F0', '252, 248, 240'),
                    ('primary', 'Warm Amber', '--primary', '#B86A3A', '184, 106, 58'),
                    ('heading', 'Soft Terracotta', '--heading', '#D4A080', '212, 160, 128'),
                    ('background', 'Warm Beige', '--background', '#F0E4D8', '240, 228, 216'),
                    ('border', 'Warm Gray', '--border', '#e8dcd0', '232, 220, 208'),
                ]
            },
            {
                'name': 'ModernEcommerce16 - Lavender',
                'category': 'ModernEcommerce16',
                'mood': 'elegant',
                'colors': [
                    ('text', 'Lavender Cream', '--text', '#F8F6FC', '248, 246, 252'),
                    ('primary', 'Soft Lavender Purple', '--primary', '#8A7AB8', '138, 122, 184'),
                    ('heading', 'Light Lavender', '--heading', '#B8A8D4', '184, 168, 212'),
                    ('background', 'Very Light Lavender', '--background', '#E4DCF0', '228, 220, 240'),
                    ('border', 'Lavender Gray', '--border', '#e0d8e8', '224, 216, 232'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE18
            # ============================================
            {
                'name': 'ModernEcommerce18 - Terracotta Brown',
                'category': 'ModernEcommerce18',
                'mood': 'warm',
                'colors': [
                    ('accent', 'Warm Cream', '--accent', '#FDF7F0', '253, 247, 240'),
                    ('secondary', 'Deep Terracotta Brown', '--secondary', '#662F17', '102, 47, 23'),
                    ('primary', 'Medium Warm Brown', '--primary', '#93523B', '147, 82, 59'),
                    ('heading', 'Warm Caramel Gold', '--heading', '#D08650', '208, 134, 80'),
                    ('background', 'Light Warm Beige', '--background', '#E3C2A3', '227, 194, 163'),
                    ('text', 'Soft Warm Gold', '--text', '#E1A16F', '225, 161, 111'),
                    ('border', 'Dark Brown', '--border', '#2E241F', '46, 36, 31'),
                    ('success', 'White', '--success', '#FFFFFF', '255, 255, 255'),
                ]
            },
            {
                'name': 'ModernEcommerce18 - Sage Green',
                'category': 'ModernEcommerce18',
                'mood': 'natural',
                'colors': [
                    ('accent', 'Sage Cream', '--accent', '#F5F8F5', '245, 248, 245'),
                    ('secondary', 'Deep Sage Green', '--secondary', '#3A6A4A', '58, 106, 74'),
                    ('primary', 'Medium Sage', '--primary', '#6A8A6A', '106, 138, 106'),
                    ('heading', 'Light Sage', '--heading', '#8AB89A', '138, 184, 154'),
                    ('background', 'Light Sage', '--background', '#D8E8D8', '216, 232, 216'),
                    ('text', 'Soft Sage', '--text', '#A8C8A8', '168, 200, 168'),
                    ('border', 'Dark Sage', '--border', '#1A2A1A', '26, 42, 26'),
                    ('success', 'White', '--success', '#FFFFFF', '255, 255, 255'),
                ]
            },
            {
                'name': 'ModernEcommerce18 - Dusty Rose',
                'category': 'ModernEcommerce18',
                'mood': 'warm',
                'colors': [
                    ('accent', 'Rose Cream', '--accent', '#FDF8F5', '253, 248, 245'),
                    ('secondary', 'Soft Dusty Rose', '--secondary', '#A85A6A', '168, 90, 106'),
                    ('primary', 'Medium Rose', '--primary', '#C87A8A', '200, 122, 138'),
                    ('heading', 'Light Rose', '--heading', '#D8A0B0', '216, 160, 176'),
                    ('background', 'Light Rose', '--background', '#F0E0E8', '240, 224, 232'),
                    ('text', 'Soft Rose', '--text', '#E8C0D0', '232, 192, 208'),
                    ('border', 'Deep Rose', '--border', '#3A2A30', '58, 42, 48'),
                    ('success', 'White', '--success', '#FFFFFF', '255, 255, 255'),
                ]
            },
            {
                'name': 'ModernEcommerce18 - Warm Amber',
                'category': 'ModernEcommerce18',
                'mood': 'warm',
                'colors': [
                    ('accent', 'Warm Ivory', '--accent', '#FCF8F0', '252, 248, 240'),
                    ('secondary', 'Warm Amber', '--secondary', '#A85A2A', '168, 90, 42'),
                    ('primary', 'Medium Amber', '--primary', '#C87A4A', '200, 122, 74'),
                    ('heading', 'Light Amber', '--heading', '#D8A06A', '216, 160, 106'),
                    ('background', 'Warm Beige', '--background', '#F0E8D8', '240, 232, 216'),
                    ('text', 'Soft Amber', '--text', '#E8C8A0', '232, 200, 160'),
                    ('border', 'Dark Brown', '--border', '#2A1A10', '42, 26, 16'),
                    ('success', 'White', '--success', '#FFFFFF', '255, 255, 255'),
                ]
            },
            {
                'name': 'ModernEcommerce18 - Lavender',
                'category': 'ModernEcommerce18',
                'mood': 'elegant',
                'colors': [
                    ('accent', 'Lavender Cream', '--accent', '#F8F6FC', '248, 246, 252'),
                    ('secondary', 'Soft Lavender Purple', '--secondary', '#7A6AAA', '122, 106, 170'),
                    ('primary', 'Medium Lavender', '--primary', '#9A8ABA', '154, 138, 186'),
                    ('heading', 'Light Lavender', '--heading', '#B8A8D4', '184, 168, 212'),
                    ('background', 'Light Lavender', '--background', '#E8E0F0', '232, 224, 240'),
                    ('text', 'Soft Lavender', '--text', '#D8D0E8', '216, 208, 232'),
                    ('border', 'Deep Lavender', '--border', '#2A2440', '42, 36, 64'),
                    ('success', 'White', '--success', '#FFFFFF', '255, 255, 255'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE19
            # ============================================
            {
                'name': 'ModernEcommerce19 - Olive Green',
                'category': 'ModernEcommerce19',
                'mood': 'natural',
                'colors': [
                    ('accent', 'Warm Cream', '--accent', '#fefaf5', '254, 250, 245'),
                    ('secondary', 'Deep Olive Green', '--secondary', '#212615', '33, 38, 21'),
                    ('primary', 'Olive Green', '--primary', '#636a2f', '99, 106, 47'),
                    ('text', 'Warm Caramel Orange', '--text', '#c07436', '192, 116, 54'),
                    ('heading', 'Warm Amber', '--heading', '#bf7f4a', '191, 127, 74'),
                    ('background', 'Bright Green', '--background', '#5c8b39', '92, 139, 57'),
                ]
            },
            {
                'name': 'ModernEcommerce19 - Coastal Teal',
                'category': 'ModernEcommerce19',
                'mood': 'cool',
                'colors': [
                    ('accent', 'Coastal Cream', '--accent', '#F5F8FA', '245, 248, 250'),
                    ('secondary', 'Deep Navy', '--secondary', '#1A2A3A', '26, 42, 58'),
                    ('primary', 'Soft Teal', '--primary', '#4A8A8A', '74, 138, 138'),
                    ('text', 'Warm Sand Orange', '--text', '#E8A060', '232, 160, 96'),
                    ('heading', 'Soft Sand', '--heading', '#D4B08A', '212, 176, 138'),
                    ('background', 'Bright Teal', '--background', '#6AAAAA', '106, 170, 170'),
                ]
            },
            {
                'name': 'ModernEcommerce19 - Dusty Rose',
                'category': 'ModernEcommerce19',
                'mood': 'warm',
                'colors': [
                    ('accent', 'Rose Cream', '--accent', '#FDF8F5', '253, 248, 245'),
                    ('secondary', 'Deep Plum', '--secondary', '#2A2028', '42, 32, 40'),
                    ('primary', 'Soft Dusty Rose', '--primary', '#B86A7A', '184, 106, 122'),
                    ('text', 'Soft Peach', '--text', '#E8A080', '232, 160, 128'),
                    ('heading', 'Light Rose', '--heading', '#D4A8B0', '212, 168, 176'),
                    ('background', 'Bright Rose', '--background', '#D48A9A', '212, 138, 154'),
                ]
            },
            {
                'name': 'ModernEcommerce19 - Warm Amber',
                'category': 'ModernEcommerce19',
                'mood': 'warm',
                'colors': [
                    ('accent', 'Warm Ivory', '--accent', '#FCF8F0', '252, 248, 240'),
                    ('secondary', 'Very Dark Brown', '--secondary', '#1A1612', '26, 22, 18'),
                    ('primary', 'Warm Golden Amber', '--primary', '#D49A4A', '212, 154, 74'),
                    ('text', 'Soft Golden', '--text', '#E8A860', '232, 168, 96'),
                    ('heading', 'Light Amber', '--heading', '#D4B06A', '212, 176, 106'),
                    ('background', 'Bright Amber', '--background', '#E8B86A', '232, 184, 106'),
                ]
            },
            {
                'name': 'ModernEcommerce19 - Lavender',
                'category': 'ModernEcommerce19',
                'mood': 'elegant',
                'colors': [
                    ('accent', 'Lavender Cream', '--accent', '#F8F6FC', '248, 246, 252'),
                    ('secondary', 'Deep Lavender', '--secondary', '#2A2440', '42, 36, 64'),
                    ('primary', 'Soft Lavender Purple', '--primary', '#8A7AB8', '138, 122, 184'),
                    ('text', 'Soft Mauve', '--text', '#D4A8C0', '212, 168, 192'),
                    ('heading', 'Light Lavender', '--heading', '#B8A8D4', '184, 168, 212'),
                    ('background', 'Bright Lavender', '--background', '#A88AC8', '168, 138, 200'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE27 (Full set)
            # ============================================
 # ============================================
            # MODERNECOMMERCE27
            # ============================================
            {
                'name': 'ModernEcommerce27 - Hazard Yellow',
                'category': 'ModernEcommerce27',
                'mood': 'industrial',
                'colors': [
                    ('text', 'Neon Yellow Green', '--text', '#DFFF19', '223, 255, 25'),
                    ('accent', 'Near Black', '--accent', '#0D0D11', '13, 13, 17'),
                    ('border', 'Dark Border', '--border', '#18181F', '24, 24, 31'),
                    ('heading', 'Warm Off White', '--heading', '#F4F4F0', '244, 244, 240'),
                    ('primary', 'Pure White', '--primary', '#FFFFFF', '255, 255, 255'),
                    ('secondary', 'Muted Gray', '--secondary', '#6B6B76', '107, 107, 118'),
                ]
            },
            {
                'name': 'ModernEcommerce27 - Safety Orange',
                'category': 'ModernEcommerce27',
                'mood': 'caution',
                'colors': [
                    ('text', 'Vivid Safety Orange', '--text', '#FF6A00', '255, 106, 0'),
                    ('accent', 'Pure Black', '--accent', '#0A0A0A', '10, 10, 10'),
                    ('border', 'Dark Border', '--border', '#1A1A1A', '26, 26, 26'),
                    ('heading', 'Cool Off White', '--heading', '#F5F5F5', '245, 245, 245'),
                    ('primary', 'Pure White', '--primary', '#FFFFFF', '255, 255, 255'),
                    ('secondary', 'Cool Gray', '--secondary', '#6E6E6E', '110, 110, 110'),
                ]
            },
            {
                'name': 'ModernEcommerce27 - Electric Cyan',
                'category': 'ModernEcommerce27',
                'mood': 'tech',
                'colors': [
                    ('text', 'Electric Cyan', '--text', '#00E5FF', '0, 229, 255'),
                    ('accent', 'Deep Carbon', '--accent', '#0A0E14', '10, 14, 20'),
                    ('border', 'Cool Dark Border', '--border', '#1A1E24', '26, 30, 36'),
                    ('heading', 'Cool White', '--heading', '#F0F4F8', '240, 244, 248'),
                    ('primary', 'Pure White', '--primary', '#FFFFFF', '255, 255, 255'),
                    ('secondary', 'Cool Slate', '--secondary', '#5A6470', '90, 100, 112'),
                ]
            },
            {
                'name': 'ModernEcommerce27 - Acid Lime',
                'category': 'ModernEcommerce27',
                'mood': 'biohazard',
                'colors': [
                    ('text', 'Acid Lime', '--text', '#A8FF00', '168, 255, 0'),
                    ('accent', 'Deep Carbon Green', '--accent', '#0A0D08', '10, 13, 8'),
                    ('border', 'Dark Green Black', '--border', '#1A1D18', '26, 29, 24'),
                    ('heading', 'Cool Mint White', '--heading', '#F2F5EE', '242, 245, 238'),
                    ('primary', 'Pure White', '--primary', '#FFFFFF', '255, 255, 255'),
                    ('secondary', 'Muted Green Gray', '--secondary', '#5A6A58', '90, 106, 88'),
                ]
            },
            {
                'name': 'ModernEcommerce27 - Blood Red',
                'category': 'ModernEcommerce27',
                'mood': 'alert',
                'colors': [
                    ('text', 'Pure Red', '--text', '#FF2A2A', '255, 42, 42'),
                    ('accent', 'Near Black', '--accent', '#0A0A0C', '10, 10, 12'),
                    ('border', 'Dark Border', '--border', '#1A1A1C', '26, 26, 28'),
                    ('heading', 'Warm Off White', '--heading', '#F5F2F2', '245, 242, 242'),
                    ('primary', 'Pure White', '--primary', '#FFFFFF', '255, 255, 255'),
                    ('secondary', 'Warm Gray', '--secondary', '#706060', '112, 96, 96'),
                ]
            },
            # ============================================
            # MODERNECOMMERCE28
            # ============================================
            {
                'name': 'ModernEcommerce28 - Classic Red',
                'category': 'ModernEcommerce28',
                'mood': 'professional',
                'colors': [
                    ('background', 'Warm', '--background', '#FAF8F5', '250, 248, 245'),
                    ('text', 'Bold Red', '--text', '#D42A2A', '212, 42, 42'),
                    ('heading', 'Black', '--heading', '#0D0D0D', '13, 13, 13'),
                    ('primary', 'Dark', '--primary', '#1A1A1A', '26, 26, 26'),
                    ('secondary', 'Light', '--secondary', '#F7F6F3', '247, 246, 243'),
                    ('accent', 'Muted Gray', '--accent', '#6B6B70', '107, 107, 112'),
                    ('border', 'Light Border', '--border', '#E8E6E1', '232, 230, 225'),
                    ('success', 'Deep Green', '--success', '#1A8A4A', '26, 138, 74'),
                    ('warning', 'Golden', '--warning', '#D49A2A', '212, 154, 42'),
                ]
            },
            {
                'name': 'ModernEcommerce28 - Terracotta',
                'category': 'ModernEcommerce28',
                'mood': 'warm',
                'colors': [
                    ('background', 'Warm', '--background', '#F5F0EA', '245, 240, 234'),
                    ('text', 'Warm Orange', '--text', '#B45D3A', '180, 93, 58'),
                    ('heading', 'Dark', '--heading', '#1E1A16', '30, 26, 22'),
                    ('primary', 'Dark', '--primary', '#2C241E', '44, 36, 30'),
                    ('secondary', 'Light', '--secondary', '#EDE8E0', '237, 232, 224'),
                    ('accent', 'Muted Warm', '--accent', '#8A7A6A', '138, 122, 106'),
                    ('border', 'Warm Border', '--border', '#D6CCC2', '214, 204, 194'),
                    ('success', 'Soft Green', '--success', '#4A7C59', '74, 124, 89'),
                    ('warning', 'Golden', '--warning', '#C6973A', '198, 151, 58'),
                ]
            },
            {
                'name': 'ModernEcommerce28 - Navy Modern',
                'category': 'ModernEcommerce28',
                'mood': 'professional',
                'colors': [
                    ('background', 'Cool', '--background', '#F4F5F7', '244, 245, 247'),
                    ('text', 'Dark Navy', '--text', '#1A1A2E', '26, 26, 46'),
                    ('heading', 'Very Dark', '--heading', '#0D0D1A', '13, 13, 26'),
                    ('primary', 'Dark', '--primary', '#16162A', '22, 22, 42'),
                    ('secondary', 'Light', '--secondary', '#F0F1F3', '240, 241, 243'),
                    ('accent', 'Muted Blue', '--accent', '#6E6E8A', '110, 110, 138'),
                    ('border', 'Light Border', '--border', '#DADCE0', '218, 220, 224'),
                    ('success', 'Deep Green', '--success', '#2D7D5A', '45, 125, 90'),
                    ('warning', 'Golden', '--warning', '#C9A84C', '201, 168, 76'),
                ]
            },
            {
                'name': 'ModernEcommerce28 - Warm Red',
                'category': 'ModernEcommerce28',
                'mood': 'warm',
                'colors': [
                    ('background', 'Warm', '--background', '#FCF8F0', '252, 248, 240'),
                    ('text', 'Bold Red', '--text', '#C0392B', '192, 57, 43'),
                    ('heading', 'Dark', '--heading', '#1C1814', '28, 24, 20'),
                    ('primary', 'Dark', '--primary', '#2A221C', '42, 34, 28'),
                    ('secondary', 'Light', '--secondary', '#F8F2E8', '248, 242, 232'),
                    ('accent', 'Muted Warm', '--accent', '#8B7A6A', '139, 122, 106'),
                    ('border', 'Warm Border', '--border', '#E5DCD0', '229, 220, 208'),
                    ('success', 'Deep Green', '--success', '#3A7D5A', '58, 125, 90'),
                    ('warning', 'Golden', '--warning', '#D4A03A', '212, 160, 58'),
                ]
            },
            {
                'name': 'ModernEcommerce28 - Muted Red',
                'category': 'ModernEcommerce28',
                'mood': 'elegant',
                'colors': [
                    ('background', 'Warm', '--background', '#EFECE6', '239, 236, 230'),
                    ('text', 'Deep Red', '--text', '#A63A3A', '166, 58, 58'),
                    ('heading', 'Dark', '--heading', '#141210', '20, 18, 16'),
                    ('primary', 'Dark', '--primary', '#1E1B17', '30, 27, 23'),
                    ('secondary', 'Light', '--secondary', '#F0EDE8', '240, 237, 232'),
                    ('accent', 'Muted Warm', '--accent', '#7A7268', '122, 114, 104'),
                    ('border', 'Warm Border', '--border', '#D6D0C6', '214, 208, 198'),
                    ('success', 'Deep Green', '--success', '#4A7A5A', '74, 122, 90'),
                    ('warning', 'Golden', '--warning', '#B8973A', '184, 151, 58'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE29
            # ============================================
            {
                'name': 'ModernEcommerce29 - Warm Orange',
                'category': 'ModernEcommerce29',
                'mood': 'warm',
                'colors': [
                    ('background', 'Warm', '--background', '#FEF8F0', '254, 248, 240'),
                    ('text', 'Bold Orange', '--text', '#E8583A', '232, 88, 58'),
                    ('heading', 'Dark', '--heading', '#1A1410', '26, 20, 16'),
                    ('primary', 'Light Warm', '--primary', '#FFEEE6', '255, 238, 230'),
                    ('secondary', 'Warm Brown', '--secondary', '#B87A5A', '184, 122, 90'),
                    ('accent', 'Light Peach', '--accent', '#F5DCC8', '245, 220, 200'),
                    ('border', 'Warm Border', '--border', '#F0DCC8', '240, 220, 200'),
                    ('success', 'Deep Green', '--success', '#2D8A5A', '45, 138, 90'),
                    ('warning', 'Golden', '--warning', '#D4A03A', '212, 160, 58'),
                ]
            },
            {
                'name': 'ModernEcommerce29 - Dark Amber',
                'category': 'ModernEcommerce29',
                'mood': 'dark',
                'colors': [
                    ('background', 'Dark', '--background', '#0D0D0D', '13, 13, 13'),
                    ('text', 'Warm Orange', '--text', '#F0A050', '240, 160, 80'),
                    ('heading', 'Light', '--heading', '#F5F0E8', '245, 240, 232'),
                    ('primary', 'Dark', '--primary', '#1A1A1A', '26, 26, 26'),
                    ('secondary', 'Muted Warm', '--secondary', '#8A8078', '138, 128, 120'),
                    ('accent', 'Dark', '--accent', '#2A2824', '42, 40, 36'),
                    ('border', 'Dark Border', '--border', '#2A2824', '42, 40, 36'),
                    ('success', 'Soft Green', '--success', '#4A9A6A', '74, 154, 106'),
                    ('warning', 'Golden', '--warning', '#D4A03A', '212, 160, 58'),
                ]
            },
            {
                'name': 'ModernEcommerce29 - Mint Fresh',
                'category': 'ModernEcommerce29',
                'mood': 'cool',
                'colors': [
                    ('background', 'Cool', '--background', '#F5F8F5', '245, 248, 245'),
                    ('text', 'Deep Teal', '--text', '#2A7A6A', '42, 122, 106'),
                    ('heading', 'Dark', '--heading', '#1A2A28', '26, 42, 40'),
                    ('primary', 'Light Mint', '--primary', '#E8F0EC', '232, 240, 236'),
                    ('secondary', 'Muted Teal', '--secondary', '#6A8A7A', '106, 138, 122'),
                    ('accent', 'Light Teal', '--accent', '#D8E4DC', '216, 228, 220'),
                    ('border', 'Soft Border', '--border', '#C8D8D0', '200, 216, 208'),
                    ('success', 'Deep Green', '--success', '#2D7D5A', '45, 125, 90'),
                    ('warning', 'Golden', '--warning', '#C9A84A', '201, 168, 74'),
                ]
            },
            {
                'name': 'ModernEcommerce29 - Warm Peach',
                'category': 'ModernEcommerce29',
                'mood': 'warm',
                'colors': [
                    ('background', 'Warm', '--background', '#F8F0E6', '248, 240, 230'),
                    ('text', 'Warm Orange', '--text', '#B85A2A', '184, 90, 42'),
                    ('heading', 'Dark', '--heading', '#1A1410', '26, 20, 16'),
                    ('primary', 'Warm', '--primary', '#F0E8DC', '240, 232, 220'),
                    ('secondary', 'Muted Warm', '--secondary', '#8A7A5A', '138, 122, 90'),
                    ('accent', 'Light Warm', '--accent', '#E4D8C8', '228, 216, 200'),
                    ('border', 'Warm Border', '--border', '#D8CAB8', '216, 202, 184'),
                    ('success', 'Deep Green', '--success', '#4A7A5A', '74, 122, 90'),
                    ('warning', 'Golden', '--warning', '#C9A03A', '201, 160, 58'),
                ]
            },
            {
                'name': 'ModernEcommerce29 - Bold Pink',
                'category': 'ModernEcommerce29',
                'mood': 'energetic',
                'colors': [
                    ('background', 'Light Gray', '--background', '#F0F0F0', '240, 240, 240'),
                    ('text', 'Bold Pink', '--text', '#FF3D7A', '255, 61, 122'),
                    ('heading', 'Black', '--heading', '#0D0D0D', '13, 13, 13'),
                    ('primary', 'White', '--primary', '#FFFFFF', '255, 255, 255'),
                    ('secondary', 'Muted Gray', '--secondary', '#7A7A8A', '122, 122, 138'),
                    ('accent', 'Light Gray', '--accent', '#F0F0F0', '240, 240, 240'),
                    ('border', 'Light Border', '--border', '#E0E0E0', '224, 224, 224'),
                    ('success', 'Green', '--success', '#00D26A', '0, 210, 106'),
                    ('warning', 'Yellow', '--warning', '#FFB800', '255, 184, 0'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE30
            # ============================================
            {
                'name': 'ModernEcommerce30 - Rose Gold',
                'category': 'ModernEcommerce30',
                'mood': 'elegant',
                'colors': [
                    ('text', 'Soft Rose', '--text', '#D47A7A', '212, 122, 122'),
                    ('background', 'Warm Pinkish Cream', '--background', '#F7F2F0', '247, 242, 240'),
                    ('border', 'Soft Warm', '--border', '#F0EAE6', '240, 234, 230'),
                    ('primary', 'Sage Green', '--primary', '#B8C8B8', '184, 200, 184'),
                    ('secondary', 'Dark Warm', '--secondary', '#2A2422', '42, 36, 34'),
                    ('accent', 'Muted Taupe', '--accent', '#A89892', '168, 152, 146'),
                    ('white', 'White', '--white', '#FFFFFF', '255, 255, 255'),
                    ('cream', 'Cream', '--cream', '#FCF8F5', '252, 248, 245'),
                    ('gold', 'Gold', '--gold', '#C9A96E', '201, 169, 110'),
                    ('gold-light', 'Light Gold', '--gold-light', '#E8D5B5', '232, 213, 181'),
                ]
            },
            {
                'name': 'ModernEcommerce30 - Coastal Teal',
                'category': 'ModernEcommerce30',
                'mood': 'cool',
                'colors': [
                    ('text', 'Deep Teal', '--text', '#3A7A8A', '58, 122, 138'),
                    ('background', 'Warm Sand', '--background', '#F5F0EA', '245, 240, 234'),
                    ('border', 'Warm Sand', '--border', '#E8E4DC', '232, 228, 220'),
                    ('primary', 'Soft Blue', '--primary', '#8AB8C8', '138, 184, 200'),
                    ('secondary', 'Dark Teal', '--secondary', '#1A2A2E', '26, 42, 46'),
                    ('accent', 'Muted Blue Gray', '--accent', '#8A9A9E', '138, 154, 158'),
                    ('white', 'White', '--white', '#FFFFFF', '255, 255, 255'),
                    ('cream', 'Cream', '--cream', '#FCFAF5', '252, 250, 245'),
                    ('gold', 'Gold', '--gold', '#C9A96E', '201, 169, 110'),
                    ('gold-light', 'Light Gold', '--gold-light', '#E8D5B5', '232, 213, 181'),
                ]
            },
            {
                'name': 'ModernEcommerce30 - Warm Amber',
                'category': 'ModernEcommerce30',
                'mood': 'warm',
                'colors': [
                    ('text', 'Warm Amber', '--text', '#C97A3A', '201, 122, 58'),
                    ('background', 'Warm Cream', '--background', '#F8F4EC', '248, 244, 236'),
                    ('border', 'Warm', '--border', '#ECE4D8', '236, 228, 216'),
                    ('primary', 'Dark Charcoal', '--primary', '#5A5A5A', '90, 90, 90'),
                    ('secondary', 'Very Dark Brown', '--secondary', '#1A1612', '26, 22, 18'),
                    ('accent', 'Muted Taupe', '--accent', '#8A8278', '138, 130, 120'),
                    ('white', 'Warm White', '--white', '#FCF8F0', '252, 248, 240'),
                    ('cream', 'Cream', '--cream', '#FAF4EC', '250, 244, 236'),
                    ('gold', 'Gold', '--gold', '#D4AF37', '212, 175, 55'),
                    ('gold-light', 'Light Gold', '--gold-light', '#E8DCC8', '232, 220, 200'),
                ]
            },
            {
                'name': 'ModernEcommerce30 - Lavender',
                'category': 'ModernEcommerce30',
                'mood': 'elegant',
                'colors': [
                    ('text', 'Soft Lavender', '--text', '#8A6A9A', '138, 106, 154'),
                    ('background', 'Lavender Cream', '--background', '#F5F0F5', '245, 240, 245'),
                    ('border', 'Soft Lavender', '--border', '#E8E4E8', '232, 228, 232'),
                    ('primary', 'Soft Purple', '--primary', '#B8A8C8', '184, 168, 200'),
                    ('secondary', 'Dark Slate', '--secondary', '#1A1A22', '26, 26, 34'),
                    ('accent', 'Muted Purple', '--accent', '#9A8A9E', '154, 138, 158'),
                    ('white', 'White', '--white', '#FFFFFF', '255, 255, 255'),
                    ('cream', 'Cream', '--cream', '#FCF8FC', '252, 248, 252'),
                    ('gold', 'Gold', '--gold', '#C9A96E', '201, 169, 110'),
                    ('gold-light', 'Light Gold', '--gold-light', '#E8D5B5', '232, 213, 181'),
                ]
            },
            {
                'name': 'ModernEcommerce30 - Sage Terracotta',
                'category': 'ModernEcommerce30',
                'mood': 'natural',
                'colors': [
                    ('text', 'Warm Terracotta', '--text', '#C47A5A', '196, 122, 90'),
                    ('background', 'Sage Cream', '--background', '#F0F0EA', '240, 240, 234'),
                    ('border', 'Soft Sage', '--border', '#E4E4DC', '228, 228, 220'),
                    ('primary', 'Sage Green', '--primary', '#A8B8A0', '168, 184, 160'),
                    ('secondary', 'Dark Sage', '--secondary', '#1E2420', '30, 36, 32'),
                    ('accent', 'Muted Sage', '--accent', '#889080', '136, 144, 128'),
                    ('white', 'Off White', '--white', '#F8F8F4', '248, 248, 244'),
                    ('cream', 'Cream', '--cream', '#F4F4EE', '244, 244, 238'),
                    ('gold', 'Gold', '--gold', '#B8A86A', '184, 168, 106'),
                    ('gold-light', 'Light Gold', '--gold-light', '#E0DCD0', '224, 220, 208'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE31
            # ============================================
            {
                'name': 'ModernEcommerce31 - Terracotta Red',
                'category': 'ModernEcommerce31',
                'mood': 'warm',
                'colors': [
                    ('accent', 'Terracotta Red', '--accent', '#E05A47', '224, 90, 71'),
                    ('accent-dark', 'Darker Red', '--accent-dark', '#C44A38', '196, 74, 56'),
                    ('dark', 'Near Black', '--dark', '#0D0D12', '13, 13, 18'),
                    ('dark-surface', 'Dark Surface', '--dark-surface', '#18181F', '24, 24, 31'),
                    ('light', 'Light Gray', '--light', '#F7F7FA', '247, 247, 250'),
                    ('light-surface', 'White', '--light-surface', '#FFFFFF', '255, 255, 255'),
                    ('muted', 'Muted Gray', '--muted', '#7A7A87', '122, 122, 135'),
                    ('muted-light', 'Lighter Gray', '--muted-light', '#A0A0B0', '160, 160, 176'),
                    ('border', 'Border', '--border', 'rgba(13,13,18,0.06)', '13, 13, 18, 0.06'),
                    ('border-firm', 'Firm Border', '--border-firm', 'rgba(13,13,18,0.12)', '13, 13, 18, 0.12'),
                    ('gold', 'Gold', '--gold', '#C9A96E', '201, 169, 110'),
                    ('gold-light', 'Light Gold', '--gold-light', '#E8D5B5', '232, 213, 181'),
                    ('success', 'Green', '--success', '#2E7D32', '46, 125, 50'),
                ]
            },
            {
                'name': 'ModernEcommerce31 - Neon Teal',
                'category': 'ModernEcommerce31',
                'mood': 'modern',
                'colors': [
                    ('accent', 'Neon Teal', '--accent', '#00D4AA', '0, 212, 170'),
                    ('accent-dark', 'Darker Teal', '--accent-dark', '#00B890', '0, 184, 144'),
                    ('dark', 'Near Black', '--dark', '#0A0A0F', '10, 10, 15'),
                    ('dark-surface', 'Dark Surface', '--dark-surface', '#12121A', '18, 18, 26'),
                    ('light', 'Cool Light Gray', '--light', '#F0F4F8', '240, 244, 248'),
                    ('light-surface', 'White', '--light-surface', '#FFFFFF', '255, 255, 255'),
                    ('muted', 'Muted Blue Gray', '--muted', '#6A7A8A', '106, 122, 138'),
                    ('muted-light', 'Lighter Blue Gray', '--muted-light', '#9AAABA', '154, 170, 186'),
                    ('border', 'Border', '--border', 'rgba(10,10,15,0.06)', '10, 10, 15, 0.06'),
                    ('border-firm', 'Firm Border', '--border-firm', 'rgba(10,10,15,0.12)', '10, 10, 15, 0.12'),
                    ('gold', 'Gold', '--gold', '#FFD700', '255, 215, 0'),
                    ('gold-light', 'Light Gold', '--gold-light', '#FFE88A', '255, 232, 138'),
                    ('success', 'Teal', '--success', '#00D4AA', '0, 212, 170'),
                ]
            },
            {
                'name': 'ModernEcommerce31 - Bold Blue',
                'category': 'ModernEcommerce31',
                'mood': 'professional',
                'colors': [
                    ('accent', 'Bold Blue', '--accent', '#2563EB', '37, 99, 235'),
                    ('accent-dark', 'Darker Blue', '--accent-dark', '#1D4ED8', '29, 78, 216'),
                    ('dark', 'Dark Navy', '--dark', '#0F172A', '15, 23, 42'),
                    ('dark-surface', 'Dark Surface', '--dark-surface', '#1E293B', '30, 41, 59'),
                    ('light', 'Cool White', '--light', '#F8FAFC', '248, 250, 252'),
                    ('light-surface', 'White', '--light-surface', '#FFFFFF', '255, 255, 255'),
                    ('muted', 'Muted Blue Gray', '--muted', '#64748B', '100, 116, 139'),
                    ('muted-light', 'Lighter Blue Gray', '--muted-light', '#94A3B8', '148, 163, 184'),
                    ('border', 'Border', '--border', 'rgba(15,23,42,0.06)', '15, 23, 42, 0.06'),
                    ('border-firm', 'Firm Border', '--border-firm', 'rgba(15,23,42,0.12)', '15, 23, 42, 0.12'),
                    ('gold', 'Amber', '--gold', '#F59E0B', '245, 158, 11'),
                    ('gold-light', 'Light Amber', '--gold-light', '#FCD34D', '252, 211, 77'),
                    ('success', 'Green', '--success', '#22C55E', '34, 197, 94'),
                ]
            },
            {
                'name': 'ModernEcommerce31 - Vibrant Orange',
                'category': 'ModernEcommerce31',
                'mood': 'energetic',
                'colors': [
                    ('accent', 'Vibrant Orange', '--accent', '#F97316', '249, 115, 22'),
                    ('accent-dark', 'Darker Orange', '--accent-dark', '#EA580C', '234, 88, 12'),
                    ('dark', 'Dark Brown Charcoal', '--dark', '#1C1917', '28, 25, 23'),
                    ('dark-surface', 'Dark Surface', '--dark-surface', '#292524', '41, 37, 36'),
                    ('light', 'Warm Cream', '--light', '#FAF7F2', '250, 247, 242'),
                    ('light-surface', 'White', '--light-surface', '#FFFFFF', '255, 255, 255'),
                    ('muted', 'Muted Warm Gray', '--muted', '#78716C', '120, 113, 108'),
                    ('muted-light', 'Lighter Warm Gray', '--muted-light', '#A8A39A', '168, 163, 154'),
                    ('border', 'Border', '--border', 'rgba(28,25,23,0.06)', '28, 25, 23, 0.06'),
                    ('border-firm', 'Firm Border', '--border-firm', 'rgba(28,25,23,0.12)', '28, 25, 23, 0.12'),
                    ('gold', 'Amber', '--gold', '#F59E0B', '245, 158, 11'),
                    ('gold-light', 'Light Amber', '--gold-light', '#FCD34D', '252, 211, 77'),
                    ('success', 'Green', '--success', '#22C55E', '34, 197, 94'),
                ]
            },
            {
                'name': 'ModernEcommerce31 - Luxe Gold',
                'category': 'ModernEcommerce31',
                'mood': 'luxurious',
                'colors': [
                    ('accent', 'Gold', '--accent', '#D4AF37', '212, 175, 55'),
                    ('accent-dark', 'Darker Gold', '--accent-dark', '#B8962E', '184, 150, 46'),
                    ('dark', 'Pure Black', '--dark', '#0D0D0D', '13, 13, 13'),
                    ('dark-surface', 'Dark Surface', '--dark-surface', '#1A1A1A', '26, 26, 26'),
                    ('light', 'Warm Parchment', '--light', '#F5F0E8', '245, 240, 232'),
                    ('light-surface', 'Warm White', '--light-surface', '#FCF8F0', '252, 248, 240'),
                    ('muted', 'Muted Taupe', '--muted', '#8A8278', '138, 130, 120'),
                    ('muted-light', 'Lighter Taupe', '--muted-light', '#B8A89A', '184, 168, 154'),
                    ('border', 'Border', '--border', 'rgba(13,13,13,0.06)', '13, 13, 13, 0.06'),
                    ('border-firm', 'Firm Border', '--border-firm', 'rgba(13,13,13,0.12)', '13, 13, 13, 0.12'),
                    ('gold', 'Gold', '--gold', '#D4AF37', '212, 175, 55'),
                    ('gold-light', 'Light Gold', '--gold-light', '#E8D5B5', '232, 213, 181'),
                    ('success', 'Green', '--success', '#2E7D32', '46, 125, 50'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE32
            # ============================================
            {
                'name': 'ModernEcommerce32 - Warm Parchment',
                'category': 'ModernEcommerce32',
                'mood': 'warm',
                'colors': [
                    ('text', 'Warm Parchment', '--text', '#F9F6F0', '249, 246, 240'),
                    ('background', 'Warm Beige', '--background', '#E3DCD2', '227, 220, 210'),
                    ('heading', 'Warm Terracotta', '--heading', '#C68A6B', '198, 138, 107'),
                    ('primary', 'Sage Green', '--primary', '#7E8F80', '126, 143, 128'),
                    ('secondary', 'Dark Charcoal', '--secondary', '#1E2221', '30, 34, 33'),
                    ('accent', 'White', '--accent', '#FFFFFF', '255, 255, 255'),
                ]
            },
            {
                'name': 'ModernEcommerce32 - Dark Gold',
                'category': 'ModernEcommerce32',
                'mood': 'dark',
                'colors': [
                    ('text', 'Near Black', '--text', '#1A1A1A', '26, 26, 26'),
                    ('background', 'Dark Brown', '--background', '#2A2824', '42, 40, 36'),
                    ('heading', 'Gold', '--heading', '#D4AF37', '212, 175, 55'),
                    ('primary', 'Muted Gray', '--primary', '#8A8A8A', '138, 138, 138'),
                    ('secondary', 'Warm Cream', '--secondary', '#F0ECE4', '240, 236, 228'),
                    ('accent', 'Dark', '--accent', '#2A2824', '42, 40, 36'),
                ]
            },
            {
                'name': 'ModernEcommerce32 - Soft Terracotta',
                'category': 'ModernEcommerce32',
                'mood': 'warm',
                'colors': [
                    ('text', 'Off White', '--text', '#FCFAF8', '252, 250, 248'),
                    ('background', 'Warm Light', '--background', '#F0ECE6', '240, 236, 230'),
                    ('heading', 'Soft Terracotta', '--heading', '#B8866A', '184, 134, 106'),
                    ('primary', 'Muted Taupe', '--primary', '#A8A09A', '168, 160, 154'),
                    ('secondary', 'Dark Brown', '--secondary', '#2A2420', '42, 36, 32'),
                    ('accent', 'White', '--accent', '#FFFFFF', '255, 255, 255'),
                ]
            },
            {
                'name': 'ModernEcommerce32 - Coastal Teal',
                'category': 'ModernEcommerce32',
                'mood': 'cool',
                'colors': [
                    ('text', 'Cool Coastal Cream', '--text', '#F5F8FA', '245, 248, 250'),
                    ('background', 'Cool Light', '--background', '#E8EEF0', '232, 238, 240'),
                    ('heading', 'Soft Teal', '--heading', '#5A8A8A', '90, 138, 138'),
                    ('primary', 'Muted Coastal', '--primary', '#8AA8A8', '138, 168, 168'),
                    ('secondary', 'Deep Navy Teal', '--secondary', '#1A2A2E', '26, 42, 46'),
                    ('accent', 'White', '--accent', '#FFFFFF', '255, 255, 255'),
                ]
            },
            {
                'name': 'ModernEcommerce32 - Warm Amber',
                'category': 'ModernEcommerce32',
                'mood': 'warm',
                'colors': [
                    ('text', 'Warm Cream', '--text', '#FCF8F0', '252, 248, 240'),
                    ('background', 'Warm Beige', '--background', '#F0E8D8', '240, 232, 216'),
                    ('heading', 'Warm Amber', '--heading', '#B86A3A', '184, 106, 58'),
                    ('primary', 'Muted Warm', '--primary', '#A89078', '168, 144, 120'),
                    ('secondary', 'Very Dark Brown', '--secondary', '#1C1612', '28, 22, 18'),
                    ('accent', 'White', '--accent', '#FFFFFF', '255, 255, 255'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE33
            # ============================================
            {
                'name': 'ModernEcommerce33 - Peach Terracotta',
                'category': 'ModernEcommerce33',
                'mood': 'warm',
                'colors': [
                    ('background', 'Warm Cream', '--background', '#FFF8F0', '255, 248, 240'),
                    ('text', 'Warm Dark Brown', '--text', '#4A3728', '74, 55, 40'),
                    ('heading', 'Warm Peach Terracotta', '--heading', '#E8A87C', '232, 168, 124'),
                    ('primary', 'Light Peach', '--primary', '#F5D5B8', '245, 213, 184'),
                    ('secondary', 'Cream', '--secondary', '#FCE9D6', '252, 233, 214'),
                    ('accent', 'Muted Rose', '--accent', '#D4A5A5', '212, 165, 165'),
                    ('border', 'Warm Beige', '--border', '#E8D5C4', '232, 213, 196'),
                    ('success', 'Soft Green', '--success', '#8CB59B', '140, 181, 155'),
                    ('warning', 'Soft Yellow', '--warning', '#F0D080', '240, 208, 128'),
                    ('error', 'Soft Red', '--error', '#D48787', '212, 135, 135'),
                ]
            },
            {
                'name': 'ModernEcommerce33 - Lavender Purple',
                'category': 'ModernEcommerce33',
                'mood': 'elegant',
                'colors': [
                    ('background', 'Lavender Cream', '--background', '#F8F4FC', '248, 244, 252'),
                    ('text', 'Deep Lavender', '--text', '#2D2440', '45, 36, 64'),
                    ('heading', 'Soft Lavender Purple', '--heading', '#B8A0D4', '184, 160, 212'),
                    ('primary', 'Light Lavender', '--primary', '#DCC8EC', '220, 200, 236'),
                    ('secondary', 'Very Light Lavender', '--secondary', '#F0E8F8', '240, 232, 248'),
                    ('accent', 'Muted Lavender', '--accent', '#B8A8C8', '184, 168, 200'),
                    ('border', 'Soft Lavender', '--border', '#E0D4E8', '224, 212, 232'),
                    ('success', 'Soft Green', '--success', '#8CB59B', '140, 181, 155'),
                    ('warning', 'Soft Yellow', '--warning', '#F0D080', '240, 208, 128'),
                    ('error', 'Soft Red', '--error', '#D48787', '212, 135, 135'),
                ]
            },
            {
                'name': 'ModernEcommerce33 - Honey Gold',
                'category': 'ModernEcommerce33',
                'mood': 'natural',
                'colors': [
                    ('background', 'Mint Cream', '--background', '#F5F8F2', '245, 248, 242'),
                    ('text', 'Deep Sage', '--text', '#2A3A2A', '42, 58, 42'),
                    ('heading', 'Warm Honey Gold', '--heading', '#C4A86A', '196, 168, 106'),
                    ('primary', 'Light Sage', '--primary', '#DCE8D0', '220, 232, 208'),
                    ('secondary', 'Very Light Sage', '--secondary', '#ECF4E8', '236, 244, 232'),
                    ('accent', 'Muted Sage', '--accent', '#A8B8A0', '168, 184, 160'),
                    ('border', 'Soft Sage', '--border', '#D4E0CC', '212, 224, 204'),
                    ('success', 'Soft Green', '--success', '#8CB59B', '140, 181, 155'),
                    ('warning', 'Soft Yellow', '--warning', '#F0D080', '240, 208, 128'),
                    ('error', 'Soft Red', '--error', '#D48787', '212, 135, 135'),
                ]
            },
            {
                'name': 'ModernEcommerce33 - Coastal Blue',
                'category': 'ModernEcommerce33',
                'mood': 'cool',
                'colors': [
                    ('background', 'Coastal Cream', '--background', '#F5F8FA', '245, 248, 250'),
                    ('text', 'Deep Navy Teal', '--text', '#1A3A4A', '26, 58, 74'),
                    ('heading', 'Soft Coastal Blue', '--heading', '#6A9AAA', '106, 154, 170'),
                    ('primary', 'Light Coastal Blue', '--primary', '#C8DCE8', '200, 220, 232'),
                    ('secondary', 'Very Light Coastal', '--secondary', '#E8F0F5', '232, 240, 245'),
                    ('accent', 'Muted Coastal', '--accent', '#A8B8C8', '168, 184, 200'),
                    ('border', 'Soft Coastal', '--border', '#D0DCE8', '208, 220, 232'),
                    ('success', 'Soft Green', '--success', '#8CB59B', '140, 181, 155'),
                    ('warning', 'Soft Yellow', '--warning', '#F0D080', '240, 208, 128'),
                    ('error', 'Soft Red', '--error', '#D48787', '212, 135, 135'),
                ]
            },
            {
                'name': 'ModernEcommerce33 - Rose Cream',
                'category': 'ModernEcommerce33',
                'mood': 'warm',
                'colors': [
                    ('background', 'Rose Cream', '--background', '#F8F5F5', '248, 245, 245'),
                    ('text', 'Deep Charcoal Rose', '--text', '#2A2428', '42, 36, 40'),
                    ('heading', 'Soft Rose', '--heading', '#C87878', '200, 120, 120'),
                    ('primary', 'Light Rose', '--primary', '#E8D0D0', '232, 208, 208'),
                    ('secondary', 'Very Light Rose', '--secondary', '#F0E8E8', '240, 232, 232'),
                    ('accent', 'Muted Rose', '--accent', '#B8A8A8', '184, 168, 168'),
                    ('border', 'Soft Rose', '--border', '#DCD0D0', '220, 208, 208'),
                    ('success', 'Soft Green', '--success', '#8CB59B', '140, 181, 155'),
                    ('warning', 'Soft Yellow', '--warning', '#F0D080', '240, 208, 128'),
                    ('error', 'Soft Red', '--error', '#D48787', '212, 135, 135'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE34
            # ============================================
            {
                'name': 'ModernEcommerce34 - Sage Green Gold',
                'category': 'ModernEcommerce34',
                'mood': 'natural',
                'colors': [
                    ('text', 'Warm Cream', '--text', '#FBF9F7', '251, 249, 247'),
                    ('heading', 'Very Dark Brown', '--heading', '#1A1513', '26, 21, 19'),
                    ('primary', 'Sage Green', '--primary', '#5B6346', '91, 99, 70'),
                    ('background', 'Warm Amber Gold', '--background', '#D99B59', '217, 155, 89'),
                    ('secondary', 'Light Warm', '--secondary', '#F2EEE5', '242, 238, 229'),
                    ('accent', 'Muted Taupe', '--accent', '#8A7A6A', '138, 122, 106'),
                    ('border', 'Warm Beige', '--border', '#C9B9A9', '201, 185, 169'),
                    ('success', 'Soft Green', '--success', '#6B8C5C', '107, 140, 92'),
                    ('warning', 'Soft Yellow', '--warning', '#E8C84A', '232, 200, 74'),
                    ('error', 'Soft Red', '--error', '#C45A4A', '196, 90, 74'),
                ]
            },
            {
                'name': 'ModernEcommerce34 - Soft Teal',
                'category': 'ModernEcommerce34',
                'mood': 'cool',
                'colors': [
                    ('text', 'Coastal Cream', '--text', '#F8FAF7', '248, 250, 247'),
                    ('heading', 'Deep Navy Teal', '--heading', '#1A2A2E', '26, 42, 46'),
                    ('primary', 'Soft Teal', '--primary', '#5A8A8A', '90, 138, 138'),
                    ('background', 'Muted Teal', '--background', '#8AB8B8', '138, 184, 184'),
                    ('secondary', 'Light Coastal', '--secondary', '#ECF2F0', '236, 242, 240'),
                    ('accent', 'Muted Teal', '--accent', '#7A9A9A', '122, 154, 154'),
                    ('border', 'Cool Beige', '--border', '#D0DCDA', '208, 220, 218'),
                    ('success', 'Soft Green', '--success', '#5A8A6A', '90, 138, 106'),
                    ('warning', 'Soft Yellow', '--warning', '#E8C84A', '232, 200, 74'),
                    ('error', 'Soft Red', '--error', '#C45A4A', '196, 90, 74'),
                ]
            },
            {
                'name': 'ModernEcommerce34 - Warm Terracotta',
                'category': 'ModernEcommerce34',
                'mood': 'warm',
                'colors': [
                    ('text', 'Warm Cream', '--text', '#FCF8F0', '252, 248, 240'),
                    ('heading', 'Very Dark Terracotta', '--heading', '#2A1A12', '42, 26, 18'),
                    ('primary', 'Warm Terracotta', '--primary', '#B86A3A', '184, 106, 58'),
                    ('background', 'Rich Terracotta', '--background', '#D48A5A', '212, 138, 90'),
                    ('secondary', 'Warm Clay', '--secondary', '#F4ECE4', '244, 236, 228'),
                    ('accent', 'Muted Taupe', '--accent', '#8A7A6A', '138, 122, 106'),
                    ('border', 'Warm Beige', '--border', '#D6C8BA', '214, 200, 186'),
                    ('success', 'Soft Green', '--success', '#5A8A5A', '90, 138, 90'),
                    ('warning', 'Soft Yellow', '--warning', '#E8C84A', '232, 200, 74'),
                    ('error', 'Soft Red', '--error', '#C45A4A', '196, 90, 74'),
                ]
            },
            {
                'name': 'ModernEcommerce34 - Lavender Purple',
                'category': 'ModernEcommerce34',
                'mood': 'elegant',
                'colors': [
                    ('text', 'Lavender Cream', '--text', '#F8F6FA', '248, 246, 250'),
                    ('heading', 'Deep Lavender', '--heading', '#2A2440', '42, 36, 64'),
                    ('primary', 'Soft Lavender Purple', '--primary', '#8A7AB8', '138, 122, 184'),
                    ('background', 'Light Lavender', '--background', '#B8A8D4', '184, 168, 212'),
                    ('secondary', 'Light Lavender', '--secondary', '#F0ECF5', '240, 236, 245'),
                    ('accent', 'Muted Lavender', '--accent', '#9A8AB0', '154, 138, 176'),
                    ('border', 'Soft Lavender', '--border', '#D8D0E8', '216, 208, 232'),
                    ('success', 'Soft Green', '--success', '#5A8A6A', '90, 138, 106'),
                    ('warning', 'Soft Yellow', '--warning', '#E8C84A', '232, 200, 74'),
                    ('error', 'Soft Red', '--error', '#C45A4A', '196, 90, 74'),
                ]
            },
            {
                'name': 'ModernEcommerce34 - Olive Green',
                'category': 'ModernEcommerce34',
                'mood': 'natural',
                'colors': [
                    ('text', 'Warm Off White', '--text', '#F5F4F0', '245, 244, 240'),
                    ('heading', 'Deep Olive', '--heading', '#1A1E18', '26, 30, 24'),
                    ('primary', 'Muted Olive Green', '--primary', '#6A7A5A', '106, 122, 90'),
                    ('background', 'Soft Olive', '--background', '#8A9A7A', '138, 154, 122'),
                    ('secondary', 'Light Warm', '--secondary', '#ECEAE4', '236, 234, 228'),
                    ('accent', 'Muted Olive', '--accent', '#8A8A7A', '138, 138, 122'),
                    ('border', 'Warm Gray', '--border', '#D0D0C8', '208, 208, 200'),
                    ('success', 'Soft Green', '--success', '#5A8A5A', '90, 138, 90'),
                    ('warning', 'Soft Yellow', '--warning', '#E8C84A', '232, 200, 74'),
                    ('error', 'Soft Red', '--error', '#C45A4A', '196, 90, 74'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE35
            # ============================================
            {
                'name': 'ModernEcommerce35 - Warm Gold',
                'category': 'ModernEcommerce35',
                'mood': 'luxurious',
                'colors': [
                    ('text', 'Near Black', '--text', '#121212', '18, 18, 18'),
                    ('heading', 'Warm Cream', '--heading', '#F9F8F5', '249, 248, 245'),
                    ('primary', 'Warm Gold', '--primary', '#C59B27', '197, 155, 39'),
                    ('secondary', 'Dark Charcoal', '--secondary', '#2E2E2C', '46, 46, 44'),
                    ('background', 'Warm Beige', '--background', '#E5E2DD', '229, 226, 221'),
                ]
            },
            {
                'name': 'ModernEcommerce35 - Platinum Gray',
                'category': 'ModernEcommerce35',
                'mood': 'modern',
                'colors': [
                    ('text', 'Near Black', '--text', '#1A1A1A', '26, 26, 26'),
                    ('heading', 'Cool Cream', '--heading', '#F5F5F0', '245, 245, 240'),
                    ('primary', 'Muted Platinum Gray', '--primary', '#8A8A9A', '138, 138, 154'),
                    ('secondary', 'Dark Charcoal', '--secondary', '#2A2A2A', '42, 42, 42'),
                    ('background', 'Cool Beige', '--background', '#E8E8E4', '232, 232, 228'),
                ]
            },
            {
                'name': 'ModernEcommerce35 - Copper Terracotta',
                'category': 'ModernEcommerce35',
                'mood': 'warm',
                'colors': [
                    ('text', 'Dark Brown', '--text', '#1A1410', '26, 20, 16'),
                    ('heading', 'Warm Sand', '--heading', '#F5F0EA', '245, 240, 234'),
                    ('primary', 'Warm Copper Terracotta', '--primary', '#B86A3A', '184, 106, 58'),
                    ('secondary', 'Dark Warm', '--secondary', '#2A221C', '42, 34, 28'),
                    ('background', 'Warm Beige', '--background', '#E8E0D8', '232, 224, 216'),
                ]
            },
            {
                'name': 'ModernEcommerce35 - Steel Blue',
                'category': 'ModernEcommerce35',
                'mood': 'cool',
                'colors': [
                    ('text', 'Dark Slate', '--text', '#0D1418', '13, 20, 24'),
                    ('heading', 'Cool White', '--heading', '#F5F7F8', '245, 247, 248'),
                    ('primary', 'Cool Steel Blue', '--primary', '#5A7A8A', '90, 122, 138'),
                    ('secondary', 'Dark Slate', '--secondary', '#1A282E', '26, 40, 46'),
                    ('background', 'Cool Beige', '--background', '#E8ECEE', '232, 236, 238'),
                ]
            },
            {
                'name': 'ModernEcommerce35 - Bronze',
                'category': 'ModernEcommerce35',
                'mood': 'warm',
                'colors': [
                    ('text', 'Dark Bronze', '--text', '#1A1612', '26, 22, 18'),
                    ('heading', 'Warm Ivory', '--heading', '#FCF8F0', '252, 248, 240'),
                    ('primary', 'Warm Bronze', '--primary', '#C49A6A', '196, 154, 106'),
                    ('secondary', 'Dark Bronze', '--secondary', '#2A2218', '42, 34, 24'),
                    ('background', 'Warm Beige', '--background', '#F0E8DC', '240, 232, 220'),
                ]
            },

            # ============================================
            # MODERNECOMMERCE36
            # ============================================
            {
                'name': 'ModernEcommerce36 - Ink Black & Electric Yellow',
                'category': 'ModernEcommerce36',
                'mood': 'industrial',
                'colors': [
                    ('background', 'Warm White', '--background', '#FFFDF5', '255, 253, 245'),
                    ('heading', 'White', '--heading', '#FFFFFF', '255, 255, 255'),
                    ('text', 'Pure Black', '--text', '#0A0A0A', '10, 10, 10'),
                    ('secondary', 'Charcoal', '--secondary', '#3A3A3A', '58, 58, 58'),
                    ('accent', 'Warm Light Border', '--accent', '#E8E4D8', '232, 228, 216'),
                    ('border', 'Pure Black', '--border', '#0A0A0A', '10, 10, 10'),
                    ('primary', 'Electric Yellow', '--primary', '#F5D000', '245, 208, 0'),
                    ('success', 'Gray', '--success', '#A0A0A0', '160, 160, 160'),
                    ('warning', 'Dark Yellow', '--warning', '#B89A00', '184, 154, 0'),
                ]
            },
            {
                'name': 'ModernEcommerce36 - Midnight & Hot Orange',
                'category': 'ModernEcommerce36',
                'mood': 'energetic',
                'colors': [
                    ('background', 'Warm Peach White', '--background', '#FFF6F0', '255, 246, 240'),
                    ('heading', 'White', '--heading', '#FFFFFF', '255, 255, 255'),
                    ('text', 'Near Black', '--text', '#0F0A05', '15, 10, 5'),
                    ('secondary', 'Dark Burnt', '--secondary', '#4A2A10', '74, 42, 16'),
                    ('accent', 'Warm Border', '--accent', '#F0DCC8', '240, 220, 200'),
                    ('border', 'Deep Espresso', '--border', '#1A0A00', '26, 10, 0'),
                    ('primary', 'Vivid Orange', '--primary', '#FF5A00', '255, 90, 0'),
                    ('success', 'Tan', '--success', '#C8A88A', '200, 168, 138'),
                    ('warning', 'Dark Orange', '--warning', '#C43A00', '196, 58, 0'),
                ]
            },
            {
                'name': 'ModernEcommerce36 - Navy & Electric Cyan',
                'category': 'ModernEcommerce36',
                'mood': 'cool',
                'colors': [
                    ('background', 'Cool Ice White', '--background', '#F0FAFF', '240, 250, 255'),
                    ('heading', 'White', '--heading', '#FFFFFF', '255, 255, 255'),
                    ('text', 'Deep Navy Black', '--text', '#001A2A', '0, 26, 42'),
                    ('secondary', 'Cool Navy', '--secondary', '#1A4A6A', '26, 74, 106'),
                    ('accent', 'Cool Border', '--accent', '#C8E4F0', '200, 228, 240'),
                    ('border', 'Deep Navy', '--border', '#001A2A', '0, 26, 42'),
                    ('primary', 'Electric Cyan', '--primary', '#00D4E0', '0, 212, 224'),
                    ('success', 'Cool Stone', '--success', '#8AB4C8', '138, 180, 200'),
                    ('warning', 'Dark Cyan', '--warning', '#008A9A', '0, 138, 154'),
                ]
            },
            {
                'name': 'ModernEcommerce36 - Burgundy & Hot Pink',
                'category': 'ModernEcommerce36',
                'mood': 'bold',
                'colors': [
                    ('background', 'Pink White', '--background', '#FFF5F8', '255, 245, 248'),
                    ('heading', 'White', '--heading', '#FFFFFF', '255, 255, 255'),
                    ('text', 'Deep Burgundy Black', '--text', '#1A0510', '26, 5, 16'),
                    ('secondary', 'Deep Plum', '--secondary', '#5A1A30', '90, 26, 48'),
                    ('accent', 'Pink Border', '--accent', '#F0D0DC', '240, 208, 220'),
                    ('border', 'Deep Burgundy', '--border', '#3A0A1A', '58, 10, 26'),
                    ('primary', 'Hot Pink', '--primary', '#FF0080', '255, 0, 128'),
                    ('success', 'Dusty Rose', '--success', '#C88AA0', '200, 138, 160'),
                    ('warning', 'Dark Pink', '--warning', '#C40060', '196, 0, 96'),
                ]
            },
            {
                'name': 'ModernEcommerce36 - Forest & Acid Green',
                'category': 'ModernEcommerce36',
                'mood': 'athletic',
                'colors': [
                    ('background', 'Light Sage', '--background', '#F0F8EC', '240, 248, 236'),
                    ('heading', 'White', '--heading', '#FFFFFF', '255, 255, 255'),
                    ('text', 'Near Black Green', '--text', '#0A1A0A', '10, 26, 10'),
                    ('secondary', 'Deep Forest', '--secondary', '#2A4A2A', '42, 74, 42'),
                    ('accent', 'Sage Border', '--accent', '#C8E0C0', '200, 224, 192'),
                    ('border', 'Deep Forest Black', '--border', '#0A1A0A', '10, 26, 10'),
                    ('primary', 'Acid Green', '--primary', '#7AF020', '122, 240, 32'),
                    ('success', 'Sage Stone', '--success', '#8AB880', '138, 184, 128'),
                    ('warning', 'Dark Green', '--warning', '#4A9A10', '74, 154, 16'),
                ]
            },
        ]