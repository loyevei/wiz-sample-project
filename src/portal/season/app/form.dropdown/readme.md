## Usage

```pug
wiz-portal-season-ui-dropdown
    ng-template('#button'='')
        button#user-menu-button(type="button", class="relative flex rounded-full bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2", aria-expanded="false", aria-haspopup="true")
            span(class="absolute -inset-1.5")
            div(class="flex items-center px-4")
                div(class="flex-shrink-0")
                    div(class="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full sm:mx-0 sm:h-10 sm:w-10 bg-gray-100")
                        svg(xmlns="http://www.w3.org/2000/svg", viewBox="0 0 20 20", fill="currentColor", class="size-5")
                            path(d="M10 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM3.465 14.493a1.23 1.23 0 0 0 .41 1.412A9.957 9.957 0 0 0 10 18c2.31 0 4.438-.784 6.131-2.1.43-.333.604-.903.408-1.41a7.002 7.002 0 0 0-13.074.003Z")
                div(class="ml-3 text-left")
                    div(class="text-base font-medium text-gray-800") {{service.auth.session.name}}
                    div(class="text-sm font-light text-gray-500") {{service.auth.session.email}}
    
    ng-template('#menu'='')
        a(routerLink="/myprofile", class="block px-4 py-2 text-sm text-gray-700", tabindex="-1") 마이페이지
        a(*ngIf="hasAuth('admin')", routerLink="/admin", class="block px-4 py-2 text-sm text-gray-700", tabindex="-1") 관리자페이지
        a(href="/auth/logout", class="block px-4 py-2 text-sm text-gray-700", tabindex="-1") 로그아웃
```
