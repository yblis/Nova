/**
 * Tailwind CSS Configuration
 * This must be loaded after the Tailwind CDN script
 */
tailwind.config = {
    darkMode: 'class',
    theme: {
        extend: {
            fontFamily: {
                sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif']
            },
            colors: {
                brand: {
                    50: '#eef6ff',
                    100: '#d9ebff',
                    200: '#b7d8ff',
                    300: '#8fc1ff',
                    400: '#64a6ff',
                    500: '#3c8dff',
                    600: '#1d74f0',
                    700: '#185ec4',
                    800: '#144e9f',
                    900: '#123f7f'
                }
            },
            boxShadow: {
                card: '0 2px 10px rgba(0,0,0,0.06)'
            }
        }
    }
};
