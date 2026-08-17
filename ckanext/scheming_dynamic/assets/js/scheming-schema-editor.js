/* Enhance the schema definition textarea with a form generated from the
 * scheming meta-schema (JSON Editor).
 *
 * The textarea stays the source of truth for the POSTed value: the module
 * keeps it in sync and falls back to plain textarea editing when JSON
 * Editor is unavailable or the current content is not parseable JSON.
 */
ckan.module('scheming-schema-editor', function ($) {
  return {
    supportedLanguages: ['en', 'de', 'it', 'es'],
    options: {
      previewUrl: null,
      previewKind: "form",
      lang: "en"
    },
    initialize: function () {
      $.proxyAll(this, /_on/);

      if (typeof window.Jedison === 'undefined') {
        return;
      }

      this.lang = this.supportedLanguages.includes(this.options.lang) ? this.options.lang : "en";
      this.textarea = this.el.get(0);
      this.form = this.textarea.form;
      this.metaSchema = JSON.parse(
        document.getElementById('scheming-meta-schema').dataset.schema
      );

      var startval = null;
      var raw = this.textarea.value.trim();

      if (raw) {
        try {
          startval = JSON.parse(raw);
        } catch (err) {
          // e.g. a form re-rendered after submitting malformed JSON:
          // keep the raw text editable instead of discarding it
          return;
        }
      }

      this._buildLayout();

      var self = this;
      this._createEditor(startval).then(function () {
        self._setFormMode(true);

        self.form.addEventListener('submit', self._onSubmit);
        self.toggle.addEventListener('click', self._onToggle);
        self.textarea.addEventListener('input', self._onTextareaInput);
        self.textarea.addEventListener('paste', self._onPaste);
        if (self.previewButton) {
          self.previewButton.addEventListener('click', self._onPreview);
          self.previewClose.addEventListener('click', self._onPreviewClose);
        }
      });
    },

    _buildLayout: function () {
      this.toolbar = document.createElement('div');
      this.toolbar.className = 'scheming-schema-editor-toolbar d-flex gap-2 py-2 mb-2';

      this.toggle = document.createElement('button');
      this.toggle.type = 'button';
      this.toggle.className = 'btn btn-secondary btn-sm';
      this.toolbar.appendChild(this.toggle);

      this.errorBox = document.createElement('div');
      this.errorBox.className = 'alert alert-danger scheming-schema-editor-errors';
      this.errorBox.hidden = true;

      this.editorHolder = document.createElement('div');
      this.editorHolder.className = 'scheming-schema-editor-form';

      var parent = this.textarea.parentNode;
      parent.insertBefore(this.toolbar, this.textarea);
      parent.insertBefore(this.errorBox, this.textarea);
      parent.insertBefore(this.editorHolder, this.textarea);

      if (this.options.previewUrl) {
        this._buildPreviewLayout();
      }
    },

    /**
     * The preview pane lives outside the <form>, so the dataset/resource
     * inputs it contains are never submitted with the schema form.
     */
    _buildPreviewLayout: function () {
      this.previewButton = document.createElement('button');
      this.previewButton.type = 'button';
      this.previewButton.className = 'btn btn-secondary btn-sm';
      this.previewButton.textContent = this.options.previewKind === 'preset'
        ? this._('Preview preset')
        : this._('Preview form');
      this.toolbar.appendChild(this.previewButton);

      this.previewToolbar = document.createElement('div');
      this.previewToolbar.className = 'scheming-schema-editor-toolbar py-2';

      this.previewClose = document.createElement('button');
      this.previewClose.type = 'button';
      this.previewClose.className = 'btn btn-secondary btn-sm';
      this.previewClose.textContent = this._('Back to editing');
      this.previewToolbar.appendChild(this.previewClose);

      this.previewContent = document.createElement('div');

      this.previewPane = document.createElement('div');
      this.previewPane.className = 'scheming-schema-preview';
      this.previewPane.hidden = true;
      this.previewPane.appendChild(this.previewToolbar);
      this.previewPane.appendChild(this.previewContent);

      this.form.parentNode.insertBefore(this.previewPane, this.form.nextSibling);
    },

    /**
     * Create the Jedison editor.
     *
     * $refs in the meta-schema (label, preset, dataset_fields items, ...)
     * only resolve when a populated RefParser is passed to Jedison.Create;
     * without it every $ref-backed field renders as a type-less switcher.
     */
    _createEditor: function (startval) {
      var self = this;
      var refParser = new Jedison.RefParser();

      return refParser.dereference(this.metaSchema).then(function () {
        self.editor = new Jedison.Create({
          container: self.editorHolder,
          theme: new Jedison.ThemeBootstrap5(),
          iconLib: 'fontawesome6',
          language: self.lang,
          schema: self.metaSchema,
          refParser: refParser,
          enableCollapseToggle: true,
          enablePropertiesToggle: true,
          btnContents: false,
          switcherInput: 'modal',
          parseMarkdown: true
        });

        if (startval) {
          self.editor.setValue(startval);
        }
      });
    },

    _setFormMode: function (formMode) {
      this.formMode = formMode;
      this.textarea.hidden = formMode;
      this.editorHolder.hidden = !formMode;
      this.toggle.textContent = formMode
        ? this._('Edit as JSON/YAML')
        : this._('Edit as form');
    },

    /**
     * Parse JSON, falling back to YAML so a copy-pasted ckanext-scheming
     * YAML schema file works too. The JSON error is what gets reported
     * when both fail, since JSON is the primary expected format.
     */
    _parseDefinition: function (raw) {
      try {
        return JSON.parse(raw);
      } catch (jsonErr) {
        if (typeof window.jsyaml === 'undefined') {
          throw jsonErr;
        }

        var parsed;

        try {
          parsed = window.jsyaml.load(raw);
        } catch (yamlErr) {
          throw jsonErr;
        }

        if (parsed === undefined || parsed === null) {
          throw jsonErr;
        }

        return parsed;
      }
    },

    _onToggle: function () {
      this._clearErrors();

      if (this.formMode) {
        this.textarea.value = JSON.stringify(this.editor.getValue(), null, 2);
        this._setFormMode(false);
        return;
      }

      var parsed;
      try {
        parsed = this._parseDefinition(this.textarea.value);
      } catch (err) {
        this._showErrors([this._('Definition is not valid JSON: ') + err.message]);
        return;
      }
      this.editor.setValue(parsed);
      this._setFormMode(true);
    },

    _onTextareaInput: function () {
      if (this.formMode) {
        return;
      }

      clearTimeout(this._textareaValidateTimer);
      var self = this;
      this._textareaValidateTimer = setTimeout(function () {
        self._validateTextarea();
      }, 300);
    },

    /**
     * Normalize a pasted YAML schema to JSON right away.
     */
    _onPaste: function () {
      if (this.formMode) {
        return;
      }

      var self = this;
      setTimeout(function () {
        var raw = self.textarea.value;

        try {
          JSON.parse(raw);
          return;
        } catch (err) {}

        var parsed;
        try {
          parsed = self._parseDefinition(raw);
        } catch (err) {
          return; // not valid YAML either; normal validation will flag it
        }

        self.textarea.value = JSON.stringify(parsed, null, 2);
        self._clearErrors();
      }, 0);
    },

    _validateTextarea: function () {
      var raw = this.textarea.value.trim();
      if (!raw) {
        this._clearErrors();
        return;
      }

      try {
        this._parseDefinition(raw);
      } catch (err) {
        this._showErrors(
          [this._('Definition is not valid JSON: ') + err.message],
          { scroll: false }
        );
        return;
      }
      this._clearErrors();
    },

    _onSubmit: function (event) {
      if (!this.formMode) {
        var parsed;
        try {
          parsed = this._parseDefinition(this.textarea.value);
        } catch (err) {
          event.preventDefault();
          this._showErrors([this._('Definition is not valid JSON: ') + err.message]);
          return;
        }
        this.textarea.value = JSON.stringify(parsed, null, 2);
        return;
      }

      this.textarea.value = JSON.stringify(this.editor.getValue(), null, 2);

      this.editor.validate();
      var errors = this.editor.getErrors();
      if (errors.length) {
        event.preventDefault();
        this._showErrors(errors.map(function (error) {
          var path = error.path.replace(/^root\.?/, '') || 'schema';
          return path + ': ' + error.message;
        }));
      }
    },

    _onPreview: function () {
      this._clearErrors();

      if (this.formMode) {
        this.textarea.value = JSON.stringify(this.editor.getValue(), null, 2);
      }

      var self = this;
      fetch(this.options.previewUrl, {
        method: 'POST',
        body: new FormData(this.form)
      })
        .then(function (response) {
          return response.text();
        })
        .then(function (html) {
          self.previewContent.innerHTML = html;
          self.form.hidden = true;
          self.previewPane.hidden = false;
          jQuery('[data-module]', self.previewContent).each(function () {
            ckan.module.initializeElement(this);
          });
        })
        .catch(function () {
          self._showErrors([self._('The preview could not be loaded.')]);
        });
    },

    _onPreviewClose: function () {
      this.previewPane.hidden = true;
      this.form.hidden = false;
    },

    _showErrors: function (messages, options) {
      var list = document.createElement('ul');
      messages.forEach(function (message) {
        var item = document.createElement('li');
        item.textContent = message;
        list.appendChild(item);
      });

      this.errorBox.innerHTML = '';
      this.errorBox.appendChild(list);
      this.errorBox.hidden = false;

      if (!options || options.scroll !== false) {
        this.errorBox.scrollIntoView({behavior: 'smooth', block: 'center'});
      }
    },

    _clearErrors: function () {
      this.errorBox.hidden = true;
      this.errorBox.innerHTML = '';
    }
  };
});
