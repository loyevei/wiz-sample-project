import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule, COMPOSITION_BUFFER_MODE } from '@angular/forms';
import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { NuMonacoEditorModule } from '@ng-util/monaco-editor';
import { SortablejsModule } from "@wiz/libs/portal/season/ngx-sortablejs";
import { KeyboardShortcutsModule } from 'ng-keyboard-shortcuts';
import { Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';

@Pipe({ name: 'safe' })
export class SafePipe implements PipeTransform {
    constructor(private domSanitizer: DomSanitizer) { }
    transform(url) {
        return this.domSanitizer.bypassSecurityTrustResourceUrl(url);
    }
}

// translate libs
import { TranslateLoader, TranslateModule } from '@ngx-translate/core';
import { TranslateHttpLoader } from '@ngx-translate/http-loader'
import { HttpClient, HttpClientModule } from '@angular/common/http';

export function createTranslateLoader(http: HttpClient) {
    return new TranslateHttpLoader(http, './assets/lang/', '.json');
}

// initialize ng module
@NgModule({
    declarations: [
        SafePipe,
        '@wiz.declarations'
    ],
    imports: [
        BrowserModule,
        AppRoutingModule,
        FormsModule,
        NgbModule,
        SortablejsModule,
        KeyboardShortcutsModule.forRoot(),
        NuMonacoEditorModule.forRoot({ baseUrl: `lib` }),
        HttpClientModule,
        TranslateModule.forRoot({
            loader: {
                provide: TranslateLoader,
                useFactory: (createTranslateLoader),
                deps: [HttpClient]
            },
            defaultLanguage: 'en'
        }),
        '@wiz.imports'
    ],
    providers: [
        {
            provide: COMPOSITION_BUFFER_MODE,
            useValue: false
        }
    ],
    bootstrap: [AppComponent]
})
export class AppModule { }